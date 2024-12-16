# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "matplotlib",
#   "seaborn",
#   "requests",
#   "scikit-learn",
#   "tabulate",
#   "python-dotenv"
# ]
# ///

import os
import sys
import argparse
import pandas as pd
import json
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN")
if not AIPROXY_TOKEN:
    print("Error: Missing AIPROXY_TOKEN environment variable.")
    sys.exit(1)

# Set up the API Token and Endpoint
url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {AIPROXY_TOKEN}",
    "Content-Type": "application/json"
}
# Define Function Schemas
feature_importance_function = {
    "name": "identify_important_features",
    "description": "Identify the most important features in a dataset based on its summary.",
    "parameters": {
        "type": "object",
        "properties": {
            "columns": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["columns"]
    }
}

feature_type_function = {
    "name": "infer_feature_types",
    "description": "Infer feature types (e.g., numeric, categorical) for dataset columns.",
    "parameters": {
        "type": "object",
        "properties": {
            "columns": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["columns"]
    }
}
# Function to Load Dataset
# Load Dataset from File
def load_dataset(file_path):
    """Loads a dataset from a given file path, with encoding fallback."""
    try:
        # Try with UTF-8 encoding
        data = pd.read_csv(file_path, encoding="utf-8")
    except UnicodeDecodeError:
        try:
            # Fallback to ISO-8859-1 encoding
            print("UTF-8 failed, trying ISO-8859-1 encoding...")
            data = pd.read_csv(file_path, encoding="ISO-8859-1")
        except Exception as e:
            print(f"Error loading dataset with fallback encodings: {e}")
            sys.exit(1)
    print(f"Loaded dataset with {data.shape[0]} rows and {data.shape[1]} columns.")
    return data

def analyze_kmeans_with_gpt(cluster_centers, data):
    """
    Send K-Means cluster centers and summarized cluster data to GPT for analysis.

    Args:
        cluster_centers (np.ndarray): Cluster center coordinates.
        data (pd.DataFrame): Dataset with cluster labels.

    Returns:
        str: GPT-generated analysis.
    """
    try:
        # Convert cluster centers to a simple list
        cluster_centers_list = cluster_centers.tolist()

        # Select numeric columns for summarizing clusters
        numeric_data = data.select_dtypes(include=["float64", "int64"])
        if "Cluster" not in numeric_data.columns:
            numeric_data = pd.concat([numeric_data, data["Cluster"]], axis=1)

        # Summarize clusters: calculate mean for numeric features
        cluster_summary = (
            numeric_data.groupby("Cluster")
            .mean()
            .round(2)
            .iloc[:, :5]  # Limit to the first 5 columns for brevity
            .to_dict()
        )

        # Prepare the GPT prompt
        prompt = (
            "Analyze the results of K-Means clustering performed on the dataset.\n\n"
            f"Cluster centers:\n{json.dumps(cluster_centers_list, indent=2)}\n\n"
            f"Cluster summary statistics (top 5 numeric features only):\n{json.dumps(cluster_summary, indent=2)}\n\n"
            "Write a detailed analysis of the clustering results."
        )

        # Debugging: Print the prompt being sent
        print("GPT Prompt:", prompt)

        # Send payload to GPT
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        # Parse and return GPT response
        result = response.json()
        print("hi",result)
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error analyzing K-Means results with GPT: {e}")
        return "GPT analysis could not be completed due to an error."


def visualize_kmeans_clusters(data):
    """
    Visualize K-Means clustering results using a scatter plot.

    Args:
        data (pd.DataFrame): Dataset with cluster labels.

    Returns:
        str: File path to the generated visualization.
    """
    try:
        if "Cluster" not in data.columns:
            print("Cluster labels are not available in the dataset for visualization.")
            return None

        numeric_cols = data.select_dtypes(include=["float64", "int64"]).columns
        if len(numeric_cols) < 2:
            print("Not enough numeric columns for scatter plot.")
            return None

        # Use the first two numeric columns for the scatter plot
        x_col, y_col = numeric_cols[:2]
        plt.figure(figsize=(8, 6))
        sns.scatterplot(
            data=data,
            x=x_col,
            y=y_col,
            hue="Cluster",
            palette="viridis",
            style="Cluster",
            s=100
        )
        plt.title("K-Means Clustering Visualization")
        plt.xlabel(x_col)
        plt.ylabel(y_col)
        plt.legend(title="Cluster")
        file_path = "kmeans_clusters.png"
        plt.savefig(file_path, bbox_inches="tight")
        plt.close()
        print(f"K-Means clustering visualization saved as {file_path}")
        return file_path
    except Exception as e:
        print(f"Error visualizing K-Means clusters: {e}")
        return None

# Summarize Dataset
def summarize_dataset(data):
    try:
        summary = {
            "columns": list(data.columns),
            "types": data.dtypes.apply(str).to_dict()
        }
        return summary
    except Exception as e:
        print(f"Error summarizing dataset: {e}")
        sys.exit(1)

# Call GPT for Feature Type Inference
def call_gpt_feature_types(summary):
    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Classify dataset columns as numeric or categorical."},
                {"role": "user", "content": f"Dataset summary: {json.dumps(summary)}"}
            ]
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        print("Feature Types Response:\n", result)
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error detecting feature types: {e}")
        return {}

# Call GPT for Feature Importance
def call_gpt_feature_importance(summary):
    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Identify the most important features in a dataset."},
                {"role": "user", "content": f"Dataset summary: {json.dumps(summary)}. Please analyze and identify key columns."}
            ],
            "functions": [feature_importance_function],
            "function_call": {
                "name": feature_importance_function["name"],
                "arguments": json.dumps({"columns": summary["columns"]})
            }
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        print("Raw GPT Response (Important Features):", json.dumps(result, indent=2))
        arguments = result["choices"][0]["message"]["function_call"]["arguments"]
        return json.loads(arguments).get("columns", [])
    except Exception as e:
        print(f"Error identifying important features: {e}")
        return []


def perform_kmeans_clustering(data, n_clusters=3):
    """
    Perform K-Means clustering on numeric columns of the dataset.

    Args:
        data (pd.DataFrame): Input dataset.
        n_clusters (int): Number of clusters.

    Returns:
        tuple: Clustered dataset and cluster centers.
    """
    from sklearn.cluster import KMeans
    from sklearn.impute import SimpleImputer

    try:
        # Select numeric data for clustering
        numeric_data = data.select_dtypes(include=["float64", "int64"])
        if numeric_data.empty:
            print("No numeric columns available for K-Means clustering.")
            return None, None

        # Handle missing values by imputing with the mean
        imputer = SimpleImputer(strategy="mean")
        numeric_data_imputed = pd.DataFrame(imputer.fit_transform(numeric_data), columns=numeric_data.columns)

        # Fit K-Means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        cluster_labels = kmeans.fit_predict(numeric_data_imputed)

        # Add cluster labels to the original dataset
        data["Cluster"] = cluster_labels

        print(f"K-Means clustering performed with {n_clusters} clusters.")
        return data, kmeans.cluster_centers_
    except Exception as e:
        print(f"Error performing K-Means clustering: {e}")
        return None, None




# Additional Analyses
def generate_analysis(summary, important_features, data):
    """
    Generate a Markdown narrative about the dataset with detailed insights.
    """
    try:
        # Prepare sample rows and key insights
        sample_rows = data.head(3).to_dict(orient="records")
        insights = []
        for col in important_features:
            if col in data.columns:
                if pd.api.types.is_numeric_dtype(data[col]):
                    insights.append({
                        "column": col,
                        "mean": data[col].mean(),
                        "median": data[col].median(),
                        "std_dev": data[col].std()
                    })
                elif pd.api.types.is_categorical_dtype(data[col]) or data[col].dtype == 'object':
                    top_values = data[col].value_counts().head(3).to_dict()
                    insights.append({
                        "column": col,
                        "top_values": top_values
                    })

        # Construct the prompt
        story_prompt = (
            "Write a detailed Markdown narrative about this dataset. Include:\n"
            f"- Columns and their types: {json.dumps(summary['types'])}\n"
            f"- Key insights about important features: {json.dumps(insights)}\n"
            f"- A summary based on the following sample rows: {json.dumps(sample_rows)}\n\n"
            "Use a friendly, engaging style suitable for a README file, and make the content insightful."
        )

        # Send request to GPT
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": story_prompt}]
        }
        response = requests.post(url, headers=headers, json=payload)

        response.raise_for_status()

        # Parse the response
        analysis = response.json()["choices"][0]["message"]["content"]
        print("Generated Analysis:\n", analysis)
        return analysis
    except Exception as e:
        print(f"Error generating analysis: {e}")
        return "An error occurred while generating the analysis."
    
# Generate Correlation Matrix
def generate_correlation_matrix(data):
    try:
        numeric_data = data.select_dtypes(include=["float64", "int64"])
        if numeric_data.empty:
            print("No numeric columns available for correlation matrix.")
            return None
        correlation_matrix = numeric_data.corr()
        plt.figure(figsize=(10, 8))
        sns.heatmap(correlation_matrix, annot=True, cmap="coolwarm", fmt=".2f")
        plt.title("Correlation Matrix")
        file_path = "correlation_matrix.png"
        plt.savefig(file_path, bbox_inches="tight")
        plt.close()
        print(f"Correlation matrix saved as {file_path}")
        return correlation_matrix, file_path
    except Exception as e:
        print(f"Error generating correlation matrix: {e}")
        return None, None

# Generate Humorous Correlation Analysis
def generate_humorous_analysis(correlation_matrix):
    try:
        correlation_dict = correlation_matrix.round(2).to_dict()
        prompt = (
            "Here's a correlation matrix:\n\n"
            f"{json.dumps(correlation_dict, indent=2)}\n\n"
            "Provide a humorous analysis of these relationships."
        )
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error generating humorous analysis: {e}")
        return "Humorous analysis could not be generated."

def clean_gpt_response(response_text):
    """
    Cleans GPT response text by removing unnecessary newlines and extra spaces.
    
    Args:
        response_text (str): Raw GPT response text with potential line breaks or extra spaces.

    Returns:
        str: Cleaned, single-line text with proper spacing.
    """
    return ' '.join(response_text.split())

def write_markdown(summary, important_features, analysis, correlation_image_path, humor, cluster_centers, kmeans_gpt_analysis, kmeans_visualization_path):
    """
    Write a detailed README.md file with insights and analysis, including a correlation matrix and K-Means visualization if available.
    """
    try:
        # Initialize content
        content = "# Dataset Analysis\n\n"

        # Summary Section
        content += "## Summary\n\n"
        content += "### Columns and Types\n"
        for col, dtype in summary["types"].items():
            content += f"- {col}: {dtype}\n"

        # Important Features Section
        content += "\n## Important Features\n\n"
        if isinstance(important_features, str):
            important_features = clean_gpt_response(important_features)
        content += important_features

        # K-Means Clustering Section
        content += "\n\n## K-Means Clustering\n\n"
        if cluster_centers is not None:
            content += "K-Means clustering performed with the following cluster centers:\n\n"
            content += f"{pd.DataFrame(cluster_centers).to_markdown(index=False)}\n"
        else:
            content += "K-Means clustering could not be performed or no numeric columns were available.\n"

        # K-Means Clustering Analysis
        content += "\n\n## K-Means Clustering Analysis\n\n"
        content += kmeans_gpt_analysis if isinstance(kmeans_gpt_analysis, str) else str(kmeans_gpt_analysis)

        # K-Means Visualization Section
        if kmeans_visualization_path:
            content += f"\n\n## K-Means Cluster Visualization\n\n![K-Means Clusters]({kmeans_visualization_path})\n"

        # Analysis Section
        content += "\n\n## Analysis\n\n"
        content += str(analysis)

        # Correlation Matrix Section
        if correlation_image_path:
            content += f"\n\n## Correlation Matrix\n\n![Correlation Matrix]({correlation_image_path})\n"

        # Humorous Analysis Section
        content += "\n\n## Humorous Analysis\n\n"
        content += str(humor)

        # Write to README.md
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(content)
        print("README.md generated successfully.")
    except Exception as e:
        print(f"Error writing README.md: {e}")


# Main Function
def main():
    parser = argparse.ArgumentParser(description="Automated dataset analysis")
    parser.add_argument("file_path", type=str, help="Path to the input CSV file")
    args = parser.parse_args()

    # Pass the file_path argument to load_dataset()
    file_path = args.file_path

    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' does not exist.")
        sys.exit(1)

    data = load_dataset(file_path)
    data, cluster_centers = perform_kmeans_clustering(data)
    summary = summarize_dataset(data)

    if cluster_centers is not None:
        kmeans_gpt_analysis = analyze_kmeans_with_gpt(cluster_centers, data)
    else:
        kmeans_gpt_analysis = "K-Means clustering analysis could not be performed due to missing results."

    kmeans_visualization_path = visualize_kmeans_clusters(data)

    feature_types = call_gpt_feature_types(summary)
    print("Feature Types:\n", feature_types)

    important_features = call_gpt_feature_importance(summary)
    print("Important Features:\n", important_features)

    # Generate detailed analysis using GPT
    analysis = generate_analysis(summary, important_features, data)

    # Generate the correlation matrix
    correlation_matrix, correlation_image_path = generate_correlation_matrix(data)

    # Generate a humorous analysis of the correlation matrix
    if correlation_matrix is not None:
        humorous_analysis = generate_humorous_analysis(correlation_matrix)
    else:
        humorous_analysis = "No numeric data available for humorous analysis."

    # Write the enhanced README file
    write_markdown(summary, "\n".join(important_features), analysis, correlation_image_path, humorous_analysis,cluster_centers,kmeans_gpt_analysis,kmeans_visualization_path)

if __name__ == "__main__":
    main()

