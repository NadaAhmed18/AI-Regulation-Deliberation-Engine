# python -m src.rag.evaluation.evaluate

import os
import json
from src.agent.retriever import KnowledgeRetrieverTool

def evaluate_retrieval():
    retriever = KnowledgeRetrieverTool()
    
    # 5 Representative Queries and the keywords we expect to find in the Top 3 results
    eval_dataset = [
        {
            "query": "What is the EU AI Act?",
            "expected_keywords": ["regulation", "risk", "framework", "european"]
        },
        {
            "query": "Does the EU AI Act ban all artificial intelligence?",
            "expected_keywords": ["not a general ban", "most", "not classified", "minimal"]
        },
        {
            "query": "What is considered an Unacceptable Risk in AI?",
            "expected_keywords": ["prohibited", "manipulation", "social scoring", "biometric"]
        },
        {
            "query": "What democratic values are protected by AI governance?",
            "expected_keywords": ["fundamental rights", "autonomy", "privacy", "rule of law"]
        },
        {
            "query": "How are General Purpose AI (GPAI) models regulated?",
            "expected_keywords": ["general-purpose", "broad range", "market", "transparency"]
        }
    ]

    print("\n" + "="*60)
    print("📊 RUNNING QUANTITATIVE RAG EVALUATION (Precision@3)")
    print("="*60)

    total_precision = 0
    
    # Data structures for file exports
    json_export_data = []
    md_table_rows = [
        "## RAG Evaluation Results",
        "",
        "| Test Query | Expected Keywords | Precision@3 (P@3) |",
        "| :--- | :--- | :---: |"
    ]

    for i, test in enumerate(eval_dataset, 1):
        query = test['query']
        expected_keywords = test['expected_keywords']
        
        print(f"\n[Test {i}/5] Query: {query}")
        
        # Retrieve Top 3 chunks (Returns the LLM-formatted string)
        raw_results = retriever.search_ai_policy(query, top_k=3)
        
        # Calculate Precision at 3 (P@3)
        hits = sum(1 for kw in expected_keywords if kw.lower() in raw_results.lower())
        p_at_3 = min(hits / len(expected_keywords), 1.0)
        total_precision += p_at_3
        
        print(f"  -> Expected Keywords: {expected_keywords}")
        print(f"  -> Score (P@3): {p_at_3:.2f}")
        
        # 1. Prepare row for Markdown Table
        kw_str = ", ".join(expected_keywords)
        md_table_rows.append(f"| {query} | {kw_str} | {p_at_3:.2f} |")
        
        # 2. Prepare payload for JSON Export
        json_export_data.append({
            "test_id": i,
            "query": query,
            "expected_keywords": expected_keywords,
            "p_at_3_score": round(p_at_3, 2),
            "retrieved_context": raw_results
        })
        
    avg_precision = total_precision / len(eval_dataset)
    md_table_rows.extend([
        "",
        f"**Average System Precision:** {avg_precision:.2f}"
    ])
    
    print("\n" + "="*60)
    print(f"✅ EVALUATION COMPLETE | Average System Precision: {avg_precision:.2f}")
    print("="*60)

    # --- SAVE FILES TO THE SAME FOLDER AS THIS SCRIPT ---
    # Get the directory where evaluate.py is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    md_filepath = os.path.join(script_dir, "evaluation_results.md")
    json_filepath = os.path.join(script_dir, "retrieved_results.json")
    
    # Write Markdown file
    with open(md_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(md_table_rows))
        
    # Write JSON file
    with open(json_filepath, "w", encoding="utf-8") as f:
        json.dump(json_export_data, f, indent=4, ensure_ascii=False)
        
    print(f"\n📁 Exported Markdown Table to: {md_filepath}")
    print(f"📁 Exported Retrieved JSON to: {json_filepath}\n")

if __name__ == "__main__":
    evaluate_retrieval()