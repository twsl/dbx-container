from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import warnings

from bs4 import BeautifulSoup
import requests
from rich.panel import Panel
from rich.table import Table

from dbx_container.models.environment import SystemEnvironment
from dbx_container.models.runtime import Runtime, RuntimeRelease
from dbx_container.utils.logging import get_logger


class RuntimeScraper:
    """Class for scraping Databricks runtime information from documentation."""

    # Base URL for the Databricks runtime documentation
    BASE_URL = "https://docs.databricks.com/aws/en/release-notes/runtime/"

    def __init__(
        self,
        max_workers: int = 5,
        verify_ssl: bool = False,
    ) -> None:
        """Initialize the RuntimeScraper.

        Args:
            max_workers: Maximum number of worker threads to use for fetching runtime data.
            verify_ssl: Whether to verify SSL certificates when making HTTP requests.
        """
        self.logger = get_logger(self.__class__.__name__)
        self.max_workers = max_workers
        self.verify_ssl = verify_ssl

        # Suppress InsecureRequestWarning if SSL verification is disabled
        if not verify_ssl:
            warnings.filterwarnings("ignore", "Unverified HTTPS request")
            self.logger.warning("SSL certificate verification is disabled")

    def _fetch_page(self, url: str) -> str:
        """Fetch page content from URL."""
        try:
            response = requests.get(url, timeout=30, verify=self.verify_ssl)
            response.raise_for_status()
            return response.text  # noqa: TRY300
        except requests.exceptions.RequestException:
            self.logger.exception(f"Error fetching page {url}")
            raise

    def _parse_date(self, date_str: str) -> date | str:
        parts = date_str.split(maxsplit=1)  # Split into first word and the rest
        if len(parts) == 2:
            month = parts[0][:3].lower()  # Take first 3 letters of month and lowercase
            rest = parts[1]
            fixed_date_str = f"{month} {rest}"
            return datetime.strptime(fixed_date_str, "%b %d, %Y").date()
        return date_str

    def _scrape_runtime_links(self) -> list[RuntimeRelease]:
        """Get links to individual runtime versions from the main page.

        Returns:
            List of RuntimeRelease objects containing version information
        """
        releases = []
        try:
            content = self._fetch_page(self.BASE_URL)
            soup = BeautifulSoup(content, "lxml")

            section = soup.find(id="all-supported-databricks-runtime-releases")
            if section is None:
                return releases
            table = section.find_next("table")
            if table is None:
                return releases

            # Process each row in the table
            entries = list(table.find_all("tr"))  # pyright: ignore[reportAttributeAccessIssue]
            table_header = entries[0]
            headers = [col.get_text() for col in table_header.find_all("th")]  # pyright: ignore[reportAttributeAccessIssue]

            if headers != ["Version", "Variants", "Apache Spark version", "Release date", "End-of-support date"]:
                return releases

            for row in entries[1:]:  # Skip header row
                cells = row.find_all("td")  # pyright: ignore[reportAttributeAccessIssue]

                version_name = cells[0].get_text().strip()

                urls = []
                base = urlparse(self.BASE_URL)
                for link in cells[1].find_all("a", href=True):  # pyright: ignore[reportAttributeAccessIssue]
                    href = link.get("href")  # pyright: ignore[reportAttributeAccessIssue]
                    full_url = urlunparse(base._replace(path=href))
                    urls.append(full_url)

                spark_version = cells[2].get_text().strip()
                release_date = cells[3].get_text().strip()
                release_date_parsed = self._parse_date(release_date)
                end_of_support_date = cells[4].get_text().strip()
                end_of_support_date_parsed = self._parse_date(end_of_support_date)

                release = RuntimeRelease(
                    version=version_name,
                    release_date=release_date_parsed,
                    end_of_support_date=end_of_support_date_parsed,
                    spark_version=spark_version,
                    url=urls[0],
                    ml_url=urls[1] if len(urls) > 1 else "",
                )
                releases.append(release)
        except Exception:
            self.logger.exception("Error getting runtime links")
        return releases

    def _extract_version_info(self, system_entries, language: str, is_ml: bool) -> str | None:
        """Extract version information for a specific language from section."""
        for li in system_entries:
            strong = li.find("strong")
            if strong is None:
                continue
            strong_text = strong.get_text().strip().lower()
            if strong_text == language:
                version = li.get_text().strip().split(": ")[1]
                return version
        return None

    def _parse_system_environment(self, soup: BeautifulSoup, is_ml: bool) -> SystemEnvironment | None:
        """Parse system environment information from the runtime page."""
        try:
            system_env_section = soup.find(id="system-environment")
            if not system_env_section:
                return None

            ul = system_env_section.find_next("ul")
            if ul is None:
                return None
            system_entries = ul.find_all("li")  # pyright: ignore[reportAttributeAccessIssue]

            operating_system = self._extract_version_info(system_entries, "operating system", is_ml)
            java_version = self._extract_version_info(system_entries, "java", is_ml)
            scala_version = self._extract_version_info(system_entries, "scala", is_ml)
            python_version = self._extract_version_info(system_entries, "python", is_ml)
            r_version = self._extract_version_info(system_entries, "r", is_ml)
            delta_lake_version = self._extract_version_info(system_entries, "delta lake", is_ml)

            return SystemEnvironment(
                operating_system=operating_system or "",
                java_version=java_version or "",
                scala_version=scala_version or "",
                python_version=python_version or "",
                r_version=r_version or "",
                delta_lake_version=delta_lake_version or "",
            )
        except Exception:
            self.logger.exception("Error parsing system environment")

        return None

    def _parse_included_libraries(self, soup: BeautifulSoup) -> dict[str, dict[str, str | tuple[str, str]]]:
        """Parse included Python libraries from the runtime page."""
        libraries = {}

        is_beta = "Beta" in soup.head.title.text  # pyright: ignore[reportOptionalMemberAccess]
        if is_beta:
            self.logger.warning("The contents of the supported environments might change during the Beta")

        # Try different section identifiers
        section_identifiers = {
            "installed-python-libraries": "python",
            "python-libraries": "python",  # For ML runtimes
            "python-libraries-on-cpu-clusters": "python",  # Alternative for ML runtimes
            "installed-r-libraries": "r",
            "r-libraries": "r",  # For ML runtimes
        }

        # First try finding by ID - only parse each language once
        parsed_languages = set()
        for id_name, lang in section_identifiers.items():
            if lang in parsed_languages:
                continue
            libraries[lang] = {}
            if section := soup.find(id=id_name):
                table = section.find_next("table")
                if table is None:
                    continue
                entries = table.find_all("tr")  # pyright: ignore[reportAttributeAccessIssue]
                if not entries:
                    continue
                header = entries[0]
                rows = entries[1:]
                headers = [col.get_text().strip() for col in header.find_all("th")]  # pyright: ignore[reportAttributeAccessIssue]

                tbl_columns = len(headers)
                multi_col = int(tbl_columns / len(set(headers)))
                for row in rows:
                    cells = row.find_all("td")  # pyright: ignore[reportAttributeAccessIssue]
                    for i in range(0, multi_col):
                        library = cells[i * 2].get_text().strip()
                        version = cells[(i * 2) + 1].get_text().strip()
                        if library:
                            libraries[lang][library] = version

                # Mark this language as parsed
                parsed_languages.add(lang)

        return libraries

    def _parse_runtime_page(self, release: RuntimeRelease, url: str) -> Runtime | None:
        content = self._fetch_page(url)
        is_ml = url.endswith("ml")
        is_lts = "lts" in url
        soup = BeautifulSoup(content, "lxml")

        system_env = self._parse_system_environment(soup, is_ml)
        if not system_env:
            self.logger.warning(f"Could not parse system environment for {url}")
            return None

        included_libraries = self._parse_included_libraries(soup)

        runtime = Runtime(
            version=release.version,
            release_date=release.release_date,
            end_of_support_date=release.end_of_support_date,
            spark_version=release.spark_version,
            url=url,
            is_ml=is_ml,
            is_lts=is_lts,
            system_environment=system_env,
            included_libraries=included_libraries,
        )
        return runtime

    def _parse_gpu_libraries(self, soup: BeautifulSoup) -> dict[str, str]:
        libraries = {}
        system_env_section = soup.find(id="system-environment")
        if not system_env_section:
            return libraries

        ul = system_env_section.find_next("ul")
        if ul is None:
            return libraries
        ul = ul.find_next("ul")
        if ul is None:
            return libraries
        system_entries = ul.find_all("li")  # pyright: ignore[reportAttributeAccessIssue]

        for li in system_entries:
            text = li.get_text().strip().lower().split(" ")
            libraries[text[0]] = text[1]
        return libraries

    def _parse_ml_runtime_page(self, release: RuntimeRelease, url: str, runtime_base: Runtime) -> Runtime | None:
        content = self._fetch_page(url)
        is_ml = url.endswith("ml")
        is_lts = "lts" in url
        soup = BeautifulSoup(content, "lxml")

        # Parse ML-specific libraries (includes ML Python packages)
        included_libraries = self._parse_included_libraries(soup)
        # Add GPU libraries specific to ML runtime
        included_libraries["gpu"] = self._parse_gpu_libraries(soup)  # pyright: ignore[reportArgumentType]

        runtime = Runtime(
            version=release.version,
            release_date=release.release_date,
            end_of_support_date=release.end_of_support_date,
            spark_version=release.spark_version,
            url=url,
            is_ml=is_ml,
            is_lts=is_lts,
            system_environment=runtime_base.system_environment,
            included_libraries=included_libraries,
        )
        return runtime

    def _parse_runtime(self, release: RuntimeRelease) -> list[Runtime]:
        """Parse a single runtime version page and return Runtime object."""
        runtimes = []
        try:
            runtime = self._parse_runtime_page(release, release.url)
            if runtime is not None:
                runtimes.append(runtime)
                if release.ml_url:
                    ml_runtime = self._parse_ml_runtime_page(release, release.ml_url, runtime)
                    if ml_runtime is not None:
                        runtimes.append(ml_runtime)
        except Exception:
            self.logger.exception(f"Error parsing runtime page {release.version}")
        return runtimes

    def get_supported_runtimes(self) -> list[Runtime]:
        """Scrape information for all available Databricks runtime versions.

        Returns:
            List of Runtime objects with information about each runtime version
        """
        runtimes = []
        try:
            # Get all runtime version links
            self.logger.info("Fetching runtime version links")
            releases = self._scrape_runtime_links()

            # Process each link with progress bar
            for release in self.logger.progress(releases, description="[green]Processing runtimes"):
                self.logger.debug(f"Processing runtime release {release.version}")
                parsed_runtimes = self._parse_runtime(release)
                if parsed_runtimes:
                    runtimes.extend(parsed_runtimes)
                else:
                    self.logger.warning(f"Could not parse runtime info for {release.version}")

            self.logger.info(f"Successfully fetched {len(runtimes)} runtime versions")
        except Exception:
            self.logger.exception("Error scraping runtimes")

        runtimes.sort(key=lambda r: r.release_date, reverse=True)

        return runtimes

    def display_runtimes(self) -> bool:
        """Display runtime information in a rich table."""
        # Create a fetcher to load or fetch runtimes

        runtimes = self.get_supported_runtimes()

        if not runtimes:
            self.logger.print(Panel("Failed to fetch runtime information.", title="Error", style="red"))
            return False

        # Create a rich table
        table = Table(title=f"Databricks Runtime Versions ({len(runtimes)} total)")
        table.add_column("Version", style="cyan", no_wrap=True)
        table.add_column("Release Date", style="green")
        table.add_column("Python", style="blue")
        table.add_column("Java", style="magenta")
        table.add_column("Scala", style="red")
        table.add_column("R", style="yellow")
        table.add_column("Delta Lake", style="white")

        # Sort runtimes by version number (newest first)
        for runtime in sorted(runtimes, key=lambda r: r.version, reverse=True):
            env = runtime.system_environment
            version = runtime.version + " (ML)" if runtime.is_ml else runtime.version
            table.add_row(
                version,
                runtime.release_date.isoformat() if isinstance(runtime.release_date, date) else runtime.release_date,
                env.python_version,
                env.java_version,
                env.scala_version,
                env.r_version,
                env.delta_lake_version,
            )

        # Print the table
        self.logger.print(table)
        self.logger.debug("Displayed runtime information successfully.")
        return True
