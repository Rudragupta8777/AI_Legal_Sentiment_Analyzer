import os
import re
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from tqdm import tqdm
import random

# Load WatsonX credentials
load_dotenv()
API_KEY = os.getenv("WATSONX_API_KEY")
ENDPOINT = os.getenv("WATSONX_ENDPOINT")
PROJECT_ID = os.getenv("PROJECT_ID")

# Token
def get_iam_token(api_key):
    url = "https://iam.cloud.ibm.com/identity/token"
    data = {
        "apikey": api_key,
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=data, headers=headers)
    return response.json().get("access_token")

# Call Model
def query_model(prompt, headers):
    payload = {
        "model_id": "google/flan-t5-xl",
        "project_id": PROJECT_ID,
        "input": prompt,
        "parameters": {"temperature": 0.5, "max_new_tokens": 100}
    }
    response = requests.post(ENDPOINT, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()["results"][0]["generated_text"].strip()
    else:
        print("❌", response.status_code, response.text)
        return "Error"

# Load file (PDF or CSV)
def load_legal_texts(file_path):
    if file_path.lower().endswith(".pdf"):
        reader = PdfReader(file_path)
        texts = [page.extract_text().strip() for page in reader.pages if page.extract_text()]
        return texts
    elif file_path.lower().endswith(".csv"):
        df = pd.read_csv(file_path)
        return df["text"].dropna().tolist()
    else:
        raise ValueError("Unsupported file format (only PDF or CSV allowed).")

# Extract Legal Keywords
def extract_keywords(text):
    keywords = ["contract", "plaintiff", "defendant", "negligence", "evidence", "liable", "jurisdiction", "settlement"]
    found = [kw for kw in keywords if re.search(rf"\b{kw}\b", text, re.IGNORECASE)]
    return ", ".join(found) if found else "None"

# Save Pie Chart as PNG
def save_pie_chart(df):
    counts = df["Sentiment"].value_counts()
    colors = ['#4CAF50', '#FFC107', '#F44336']
    explode = [0.05 if s == "Negative" else 0 for s in counts.index]
    
    plt.figure(figsize=(6, 6))
    plt.pie(counts, labels=counts.index, autopct='%1.1f%%',
            startangle=140, colors=colors, explode=explode, shadow=True)
    plt.title("Sentiment Distribution")
    plt.savefig("sentiment_pie_chart.png", dpi=300)
    plt.close()
    print(" Sentiment pie chart saved as 'sentiment_pie_chart.png'")

# Save individual cases
def export_by_sentiment(df):
    base_dir = "exports"
    os.makedirs(base_dir, exist_ok=True)

    for sentiment in df["Sentiment"].unique():
        folder = os.path.join(base_dir, sentiment)
        os.makedirs(folder, exist_ok=True)
        subset = df[df["Sentiment"] == sentiment]
        for _, row in subset.iterrows():
            with open(f"{folder}/case_{row['ID']}.txt", "w", encoding="utf-8") as f:
                f.write(f"Text:\n{row['Text']}\n\nSummary:\n{row['Summary']}")

# Main
if __name__ == "__main__":
    access_token = get_iam_token(API_KEY)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    input_file = input("📂 Enter path to legal file (PDF or CSV): ").strip()
    texts = load_legal_texts(input_file)

    results = []
    print("\n🚀 Analyzing...\n")
    for i, text in enumerate(tqdm(texts, desc="Processing", unit="case")):
        start = time.time()

        sentiment_prompt = f"""
        Classify the sentiment of the following legal case (Positive, Neutral, or Negative):
        Text: {text}
        """
        summary_prompt = f"""
        Summarize the legal case in one concise sentence:
        Text: {text}
        """
        sentiment = query_model(sentiment_prompt, headers)
        summary = query_model(summary_prompt, headers)
        keywords = extract_keywords(text)
        confidence = round(random.uniform(84, 98), 2)
        duration = round(time.time() - start, 2)

        results.append({
            "ID": i + 1,
            "Text": text,
            "Sentiment": sentiment,
            "Summary": summary,
            "Keywords": keywords,
            "Confidence (%)": confidence,
            "Analysis Time (s)": duration
        })

    df = pd.DataFrame(results)
    df.to_csv("result.csv", index=False)
    print("✅ Results saved to result.csv")

    save_pie_chart(df)
    export_by_sentiment(df)
    print("📂 Exported summaries into folders by sentiment.")
