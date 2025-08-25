import pandas as pd
from pathlib import Path
import re

def template_to_regex(template: str) -> str:
    """Convert a template with placeholders like {GENDER1} to a regex pattern"""
    pattern = re.escape(template)
    pattern = re.sub(r'\\\{[^}]+\\\}', r'(.+?)', pattern)
    return f"^{pattern}$"

class DataLoader:
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def load_data(self) -> pd.DataFrame:
        records = []
        for csv_file in self.root_dir.rglob("*_global_evaluation.csv"):
            df = pd.read_csv(csv_file, sep=";")
            for _, row in df.iterrows():
                records.append({
                    "Model": row["Model"],
                    "Language": row["Language"],
                    "Concern": row["Concern"],  # <- ADD THIS
                    "Passed Pct": float(row["Passed Pct"])  # Keep as decimal (0-1)
                })
        return pd.DataFrame(records)
    
    def load_failed_cases(self) -> pd.DataFrame:
        """
        Return DataFrame with columns:
        [Language, Model, Template, Instance, Response, Group ID]
        Processes failures strictly per model from inside the files.
        """
        all_failed_cases = []
        group_id_counter = 0

        # Iterate over all evaluation files
        for eval_file in self.root_dir.rglob("*_evaluation*.csv"):
            if "_global_evaluation" in str(eval_file):
                continue  # Skip global summary files

            # Extract language from path
            rel_parts = eval_file.relative_to(self.root_dir).parts
            language = rel_parts[0]

            # Load evaluation file
            eval_df = pd.read_csv(eval_file, sep=";")
            if "Model" not in eval_df.columns:
                print(f"[WARNING] Missing 'Model' column in {eval_file.name}")
                continue

            # Load corresponding response file
            response_file = eval_file.parent / eval_file.name.replace("_evaluations", "_responses")
            if not response_file.exists():
                print(f"[WARNING] No response file for {eval_file.name}")
                continue
            resp_df = pd.read_csv(response_file, sep=";")

            # Process each model present in this file
            for model in eval_df["Model"].unique():
                eval_model_df = eval_df[eval_df["Model"] == model]
                resp_model_df = resp_df[resp_df["Model"] == model] if "Model" in resp_df.columns else resp_df

                # Get all failed templates for this model
                failed_templates = eval_model_df.loc[eval_model_df["Evaluation"] == "Failed", "Template"]

                # Match failures to responses for this specific model
                for template in failed_templates:
                    regex = template_to_regex(template)
                    group_id_counter += 1

                    matching_responses = resp_model_df[resp_model_df["Instance"].str.match(regex)]
                    for _, row in matching_responses.iterrows():
                        all_failed_cases.append({
                            "Language": language,
                            "Model": model,
                            "Template": template,
                            "Instance": row["Instance"],
                            "Response": row["Response"],
                            "Group ID": group_id_counter
                        })
        return pd.DataFrame(all_failed_cases)
    

    def count_total_responses_rows(self) -> int:
        total_rows = 0
        for response_file in self.root_dir.rglob("*_responses.csv"):
            try:
                df = pd.read_csv(response_file, sep=";")
                total_rows += len(df)
            except Exception as e:
                print(f"[ERROR] Failed to read {response_file.name}: {e}")
        return total_rows
