import os
from dotenv import load_dotenv
import glob
from typing import Optional
from datetime import datetime
import arxiv
from llama_parse import LlamaParse

from get_repo_root import find_repo_root

load_dotenv()
LLAMAPARSE_API_KEY = os.environ.get("LLAMAPARSE_API_KEY", None)

class ArxivService:

    def __init__(self):
        self.project_root = find_repo_root()
        self.parser = LlamaParse(
            api_key=LLAMAPARSE_API_KEY,
            result_type="markdown"
        )
        self.arxiv_client = arxiv.Client()

    def search_arxiv_papers(self, topic: Optional[str] = "RAG Retrieval Augmented Generation", start_date: Optional[str] = None, end_date: Optional[str] = None, max_results: Optional[int] = 10) -> str:

        # Convert start_date and end_date to datetime objects if they are strings
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Build the query with an optional date range
        query = f"{topic}"

        # Add date range to the query if dates are provided
        if start_date and end_date:
            start_date_str = start_date.strftime("%Y%m%d")
            end_date_str = end_date.strftime("%Y%m%d")
            query += f" submittedDate:[{start_date_str} TO {end_date_str}]"

        # Perform the search
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            #sort_by=arxiv.SortCriterion.SubmittedDate,
            #sort_order=arxiv.SortOrder.Descending
        )
        print("SEARCH PARAMS: ", search)

        # Display the search results
        titles = []
        descriptions = []
        for result in self.arxiv_client.results(search):
            print("Title:", result.title)
            print("Authors:", ", ".join(author.name for author in result.authors))
            print("Published:", result.published.date())
            print("URL:", result.entry_id)
            print("Categories:", result.categories)
            print("Summary:", result.summary)
            print("-" * 40)

            if f'{result.title}.pdf' in glob.glob(os.path.join(self.project_root, "src/playground/input/arxiv/*.pdf")):
                print(f"PDF for {result.title} already exists. Skipping download...")
                continue
            else:
                result.download_pdf(dirpath=os.path.join(self.project_root, "src/playground/input/arxiv"), filename=f'{result.title}.pdf')
                titles.append(result.title)
                descriptions.append(result.summary)

        return titles, descriptions

    async def parse_pdfs(self) -> None:

        pdf_dir = os.path.join(self.project_root, "src/playground/input/arxiv")
        pdf_filepaths = glob.glob(os.path.join(pdf_dir, "*.pdf"))

        for fp in pdf_filepaths:
            if fp.replace(".pdf", ".md") in glob.glob(os.path.join(self.project_root, "src/playground/input/md/*.md")):
                print(f"Markdown file for {title} already exists. Skipping parsing...")
            else:
                try:
                    pages = await self.parser.aload_data(fp)
                    with open(os.path.join(self.project_root, "src/playground/input/md", f'{fp.split("/")[-1].replace(".pdf", ".md")}'), "w", encoding="utf-8") as f:
                        document = "\n".join([page.text for page in pages])
                        f.write(document)
                    os.remove(fp)
                except Exception as e:
                    print(f"Error parsing {fp}: {e}")
                    continue

arxiv_service = ArxivService()
