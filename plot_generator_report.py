import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

# Set global matplotlib parameters
plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 14,
    'axes.labelsize': 13,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'legend.fontsize': 12,
    'figure.titlesize': 16
})

class PlotGenerator:
    def __init__(self, df: pd.DataFrame, plot_dir: Path):
        self.df = df
        self.plot_dir = plot_dir
        self.plot_dir.mkdir(parents=True, exist_ok=True)

    def generate(self):
        plots = []
        concerns = self.df["Concern"].unique()
        for concern in concerns:
            df_concern = self.df[self.df["Concern"] == concern]
            
            models = df_concern["Model"].unique()
            languages = df_concern["Language"].unique()
            
            if len(models) > 1 and len(languages) > 1:
                label = f"Concern: {concern}"
                plot_path = self._plot_grouped_bar(df_concern, label=label)
                plots.append((label, plot_path))
            else:
                if len(models) == 1:
                    df_avg = df_concern.groupby("Language")["Passed Pct"].mean().reset_index()
                    label = f"Concern: {concern} (Model: {models[0]})"
                    plot_path = self._plot_bar(df_avg, x="Language", y="Passed Pct", label=label)
                else:
                    df_avg = df_concern.groupby("Model")["Passed Pct"].mean().reset_index()
                    label = f"Concern: {concern}"
                    plot_path = self._plot_bar(df_avg, x="Model", y="Passed Pct", label=label)
                plots.append((label, plot_path))

        return plots

    def _plot_grouped_bar(self, df: pd.DataFrame, label: str = "") -> Path:
        # Wide but not too tall figure (16:9 ratio)
        fig, ax = plt.subplots(figsize=(12, 6))  # Width: 12", Height: 6"
        
        models = df["Model"].unique()
        languages = df["Language"].unique()
        
        display_languages = []
        for code in languages:
            lang_code = code.split('_')[0].upper()
            if lang_code == "LU":
                lang_code = "LB"
            display_languages.append(lang_code)
        
        data = {}
        for model in models:
            model_data = []
            for lang in languages:
                avg_pct = df[(df["Model"] == model) & (df["Language"] == lang)]["Passed Pct"].mean() * 100
                model_data.append(avg_pct)
            data[model] = model_data
        
        n_models = len(models)
        n_languages = len(languages)
        bar_width = 0.35
        index = np.arange(n_languages)
        
        colors = plt.cm.tab10.colors[:n_models]  # Only take needed colors
        bars = []
        for i, (model, values) in enumerate(data.items()):
            bar_pos = index + i * bar_width
            bars.append(ax.bar(
                bar_pos, values, bar_width,
                label=model,
                color=colors[i],
                alpha=0.8
            ))
            
            for j, (pos, value) in enumerate(zip(bar_pos, values)):
                ax.text(
                    pos, value + 1, f'{value:.1f}%',
                    ha='center', va='bottom',
                    fontsize=12,
                    fontweight='bold'
                )

        ax.set_xticks(index + bar_width * (n_models - 1) / 2)
        ax.set_xticklabels(display_languages, fontweight='bold')
        ax.set_ylabel("Passed Percentage (%)", fontweight='bold')
        ax.set_ylim(0, 105)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Place legend at upper center above the plot
        ax.legend(bbox_to_anchor=(0.5, 1.15), loc='upper center', ncol=n_models)
        
        if label:
            ax.set_title(label, pad=15, fontweight='bold')
            
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        safe_label = label.replace(" ", "_").replace(":", "").lower()
        filename = f"plot_{safe_label}.png"
        path = self.plot_dir / filename

        plt.tight_layout()
        plt.savefig(path, dpi=120, bbox_inches='tight', facecolor='white')
        plt.close()
        return path

    def _plot_bar(self, df: pd.DataFrame, x: str, y: str, label: str = "") -> Path:
        # Slightly wider than tall (3:2 ratio)
        fig, ax = plt.subplots(figsize=(9, 6))  # Width: 9", Height: 6"
        
        percentages = df[y] * 100

        display_labels = df[x]
        if x == "Language":
            display_labels = []
            for code in df[x]:
                lang_code = code.split('_')[0].upper()
                if lang_code == "LU":
                    lang_code = "LB"
                display_labels.append(lang_code)

        bars = ax.bar(
            range(len(display_labels)), 
            percentages, 
            color='steelblue', 
            alpha=0.8, 
            width=0.7
        )

        ax.set_xticks(range(len(display_labels)))
        ax.set_xticklabels(display_labels, fontweight='bold')
        ax.set_ylabel("Passed Percentage (%)", fontweight='bold')
        ax.set_ylim(0, 105)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        for i, (bar, pct) in enumerate(zip(bars, percentages)):
            ax.text(
                bar.get_x() + bar.get_width() / 2, 
                bar.get_height() + 1.5,
                f'{pct:.1f}%', 
                ha='center', 
                va='bottom', 
                fontweight='bold',
                fontsize=12
            )

        if label:
            ax.set_title(label, pad=15, fontweight='bold')
            
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        safe_label = label.replace(" ", "_").replace(":", "").lower()
        filename = f"plot_{safe_label}.png"
        path = self.plot_dir / filename

        plt.tight_layout()
        plt.savefig(path, dpi=120, bbox_inches='tight', facecolor='white')
        plt.close()
        return path