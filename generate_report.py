import os
import sys
import json
from pathlib import Path
from datetime import datetime
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from dotenv import load_dotenv
from data_loader_report import DataLoader
from plot_generator_report import PlotGenerator
import pandas as pd

# Load environment variables
load_dotenv()

# Resolve and validate environment paths
def get_env_path(var_name):
    value = os.getenv(var_name)
    if value is None:
        raise EnvironmentError(f"{var_name} is not set in the .env file.")
    return Path(value)

CONFIG_PATH = get_env_path("CONFIG_PATH")

class ConfigLoader:
    @staticmethod
    def find_config(root: Path) -> dict:
        for path in root.rglob("config.json"):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        raise FileNotFoundError("No config.json found.")
    
class LogoCanvas(canvas.Canvas):
    def __init__(self, *args, logo_filename: str = "logo.png", **kwargs):
        self.logo_filename = logo_filename
        super().__init__(*args, **kwargs)

    def drawImageIfExists(self):
        logo_file =  Path("logo") / self.logo_filename
        if logo_file.exists():
            try:
                # Try different positions and sizes to make logo more visible
                self.drawImage(str(logo_file), x=1.5*cm, y=A4[1] - 3*cm, width=3*cm, height=2*cm, preserveAspectRatio=True)
                print(f"[INFO] Logo drawn from {logo_file}")
            except Exception as e:
                print(f"[WARNING] Could not draw logo: {e}")
        else:
            print(f"[WARNING] Logo file not found: {logo_file}")

    def showPage(self):
        self.drawImageIfExists()
        super().showPage()

    def save(self):
        self.drawImageIfExists()
        super().save()


class PDFReport:
    def __init__(self, output_path: Path, config: dict, plots: list[tuple[str, Path]], failed_cases: dict, total_tests: int, timestamp: str):
        self.output_path = output_path
        self.config = config
        self.plots = plots
        self.failed_cases = failed_cases
        self.total_tests = total_tests
        self.timestamp = timestamp
        self.styles = getSampleStyleSheet()

    def generate(self):
        doc = SimpleDocTemplate(str(self.output_path), pagesize=A4)
        story = []

        story.extend(self._build_header())
        story.extend(self._build_requirements_table())
        story.extend(self._build_plots())
        story.extend(self._build_failed_cases_section())

        doc.build(story, canvasmaker=lambda *a, **kw: LogoCanvas(*a, logo_path="logo.png", **kw))
        print(f"[INFO] PDF saved to {self.output_path}")

    def _build_header(self) -> list:
        elems = [
            Paragraph("Evaluation Report", self.styles["Title"]),
            Spacer(1, 6),
            Paragraph(f"<b>Timestamp:</b> {self.format_timestamp(self.timestamp)}", self.styles["Normal"]),
            Paragraph("Input", self.styles["Heading2"]),
            Spacer(1, 6),
        ]
        if "config_filename" in self.config:
            elems.append(Paragraph(f"<b>Config file:</b> {self.config['config_filename']}", self.styles["Normal"]))
            
            with open(f"{CONFIG_PATH}/{self.config['config_filename']}", "r", encoding="utf-8") as f:
                content = json.load(f)
                input_lang = self._format_lang_code(content['inputLanguage'])
                target_langs = ", ".join(self._format_lang_code(l) for l in content['translateInto'])

                elems.append(Paragraph(f"<b>Original language:</b> {input_lang}", self.styles["Normal"]))
                elems.append(Paragraph(f"<b>Target languages:</b> {target_langs}", self.styles["Normal"]))
                elems.append(Paragraph(f"<b>Number of paraphrases:</b> {content['nParaphrases']}", self.styles["Normal"]))
                elems.append(Paragraph(f"<b>Model used for translation and paraphrasing:</b> {content['llm']}", self.styles["Normal"]))
                elems.append(Paragraph(f"<b>Total number of test prompts successfully executed:</b> {self.total_tests}", self.styles["Normal"]))

        if "prompts_filename" in self.config:
            elems.append(Paragraph(f"<b>Prompt file:</b> {self.config['prompts_filename']}", self.styles["Normal"]))

        elems.append(Spacer(1, 20))
        return elems

    def _build_requirements_table(self) -> list:
        elems = []

        requirements = self.config["config"].get("requirements", [])
        if not requirements:
            elems.append(Paragraph("No concerns defined in the configuration.", self.styles["Normal"]))
            return elems

        for i, req in enumerate(requirements, 1):
            concern = req.get("concern", "")
            markup = req.get("markup", "")
            elems.append(Paragraph(f"<b>Target category {i}:</b> {concern} — <b>Markup:</b> {markup}", self.styles["Heading3"]))
            elems.append(Spacer(1, 6))

            communities = req.get("communities", {})
            elems.append(Paragraph("Communities:"))
            langs = sorted(communities.keys())
            lang_headers = [self._format_lang_code(l) for l in langs]

            table_data = [lang_headers]
            max_len = max(len(v) for v in communities.values())
            for i in range(max_len):
                table_data.append([
                    communities[lang][i] if i < len(communities[lang]) else "" for lang in langs
                ])

            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            elems.append(table)
            elems.append(Spacer(1, 20))

        return elems


    def _build_plots(self) -> list:
        elems = [Paragraph("Results", self.styles["Heading2"])]
        for label, plot in self.plots:
            elems.append(Paragraph(label, self.styles["Heading4"]))
            elems.append(Image(str(plot), width=300, height=200))
            elems.append(Spacer(1, 20))
        return elems

    def _build_failed_cases_section(self) -> list:
        """Build section showing failed test cases grouped by Language → Model."""
        if self.failed_cases.empty:
            return []
        
        self._validate_failed_cases_columns()
        
        section = [
            Paragraph("Failed Cases Analysis", self.styles["Heading2"]),
            Spacer(1, 10)
        ]
        
        for language, lang_group in self.failed_cases.groupby("Language"):
            section.extend(self._build_language_section(language, lang_group))
            section.append(Spacer(1, 20))  # Space between languages
            
        return section

    def _validate_failed_cases_columns(self) -> None:
        """Validate that required columns exist in failed_cases DataFrame."""
        if "Model" not in self.failed_cases.columns:
            raise KeyError(
                "Column 'Model' not found in failed_cases; cannot group by model."
            )

    def _build_language_section(self, language: str, lang_group: pd.DataFrame) -> list:
        """Build section for a specific language containing all its models."""
        section = [
            Paragraph(
                f"Language: {self._format_lang_code(language)}",
                self.styles["Heading3"]
            ),
            Spacer(1, 6)
        ]
        
        for model, model_group in lang_group.groupby("Model"):
            section.extend(self._build_model_section(model, model_group))
            
        return section

    def _build_model_section(self, model: str, model_group: pd.DataFrame) -> list:
        """Build section for a specific model within a language."""
        section = [
            Paragraph(f"Model: <b>{model}</b>", self.styles["Heading4"]),
            Spacer(1, 4),
            self._create_failures_table(model_group),
            Spacer(1, 12)
        ]
        return section

    def _create_failures_table(self, failures: pd.DataFrame) -> Table:
        """Create a table with alternating colors for template groups."""
        # Table header
        table_data = [[
            Paragraph("<b>Template</b>", self.styles["Normal"]),
            Paragraph("<b>Instance</b>", self.styles["Normal"]),
            Paragraph("<b>Response</b>", self.styles["Normal"]),
        ]]
        
        # Base table styles
        table_styles = [
            ('GRID', (0, 0), (-1, -1), 0.3, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            # Header row style
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]
        
        previous_template = None
        current_color = colors.white  # Start with white
        row_index = 1  # Start after header
        
        for _, row in failures.iterrows():
            current_template = row["Template"]
            
            # Change color when template changes
            if previous_template is not None and current_template != previous_template:
                current_color = (
                    colors.lightblue if current_color == colors.white 
                    else colors.white
                )
            
            # Add row with current color
            table_data.append([
                Paragraph(str(current_template), self.styles["Normal"]),
                Paragraph(str(row["Instance"]), self.styles["Normal"]),
                Paragraph(str(row["Response"]), self.styles["Normal"]),
            ])
            
            # Apply background color to this row
            table_styles.append(
                ('BACKGROUND', (0, row_index), (-1, row_index), current_color))
            
            previous_template = current_template
            row_index += 1
        
        tbl = Table(
            table_data,
            colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm],
        )
        tbl.setStyle(TableStyle(table_styles))
        return tbl

    def _add_template_separator_if_needed(self, styles: list, 
                                        prev_template: str, 
                                        curr_template: str, 
                                        row_index: int) -> None:
        """Add visual separator between different templates in the table."""
        if prev_template is not None and curr_template != prev_template:
            styles.append(
                ('LINEABOVE', (0, row_index), (-1, row_index), 1.5, colors.black)
            )


    def _format_lang_code(self, lang: str) -> str:
        code = lang.split('_')[0].upper()
        return "LB" if code == "LU" else code

    def format_timestamp(self, ts: str) -> str:
        try:
            dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
            return dt.strftime("%B %d, %Y at %H:%M")
        except ValueError:
            return ts

    def format_timestamp(self, ts: str) -> str:
        try:
            dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
            return dt.strftime("%B %d, %Y at %H:%M")
        except ValueError:
            return ts

class ReportController:
    
    def __init__(self, base_dir: Path, report_dir: Path):
        self.base_dir = base_dir
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(self, timestamp: str = None):
        target = self._resolve_timestamp_dir(timestamp)
        data_loader = DataLoader(target)
        df = data_loader.load_data()
        config = ConfigLoader.find_config(target)
        
        # Load failed cases for analysis
        failed_cases = data_loader.load_failed_cases()
        total_tests = data_loader.count_total_responses_rows()
        
        plot_dir = Path("temp_plots")
        plots = PlotGenerator(df, plot_dir).generate()
        output_pdf = self.report_dir / f"report_{target.name}.pdf"
        PDFReport(output_pdf, config, plots, failed_cases, total_tests, timestamp=target.name).generate()

    def _resolve_timestamp_dir(self, ts: str) -> Path:
        if ts:
            path = self.base_dir / ts
            if not path.exists():
                raise FileNotFoundError(f"Timestamp folder not found: {path}")
            return path
        timestamps = sorted(
            [d for d in self.base_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime
        )
        if not timestamps:
            raise FileNotFoundError("No timestamp folders found.")
        print(f"[INFO] Using latest timestamp: {timestamps[-1].name}")
        return timestamps[-1]

if __name__ == "__main__":
    REMOTE_RESULTS_PATH = Path(os.getenv("REMOTE_RESULTS_PATH"))
    REMOTE_SAVE_PATH = os.getenv("REMOTE_SAVE_PATH")
    
    # Get subfolder name from sys.argv
    subfolder_name = sys.argv[1] if len(sys.argv) > 1 else None
    arg_timestamp = sys.argv[2] if len(sys.argv) > 2 else None

    if not subfolder_name:
        raise ValueError("You must provide a folder name as the first argument.")

    base_path = REMOTE_RESULTS_PATH / REMOTE_SAVE_PATH / subfolder_name
    report_path = Path("reports")

    ReportController(base_path, report_path).run(arg_timestamp)