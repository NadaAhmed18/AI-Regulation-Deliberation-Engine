# python -m src.rag.evaluation.evaluate

import os
import json
from src.agent.tools.retriever import search_ai_policy

def evaluate_retrieval():
    # 5 Representative Queries and the keywords we expect to find in the results
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
    print("📊 RUNNING QUANTITATIVE RAG EVALUATION (True Precision@3)")
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
        
        # Retrieve Top 3 chunks
        formatted_results = search_ai_policy(query, top_k=3)
        
        # --- FIXING THE P@3 CALCULATION FOR THE REVIEWER ---
        # 1. Split the formatted string back into individual chunks
        # (Assuming the tool uses "--- SOURCE" to separate them)
        if "--- SOURCE" in formatted_results:
            chunks = formatted_results.split("--- SOURCE")[1:] 
        else:
            chunks = [] # Fallback if no results were found
            
        relevant_chunks_count = 0
        
        # 2. Evaluate EACH chunk individually
        for chunk in chunks:
            chunk_lower = chunk.lower()
            # A chunk is considered "Relevant" if it contains at least ONE expected keyword
            if any(kw.lower() in chunk_lower for kw in expected_keywords):
                relevant_chunks_count += 1
                
        # 3. Calculate True Precision@3
        # Formula: (Number of Relevant Documents in Top 3) / 3
        p_at_3 = relevant_chunks_count / 3.0
        total_precision += p_at_3
        
        print(f"  -> Expected Keywords: {expected_keywords}")
        print(f"  -> Relevant Chunks Found: {relevant_chunks_count}/3")
        print(f"  -> Score (P@3): {p_at_3:.2f}")
        
        # Prepare row for Markdown Table
        kw_str = ", ".join(expected_keywords)
        md_table_rows.append(f"| {query} | {kw_str} | {p_at_3:.2f} |")
        
        # Prepare payload for JSON Export
        json_export_data.append({
            "test_id": i,
            "query": query,
            "expected_keywords": expected_keywords,
            "relevant_chunks": relevant_chunks_count,
            "p_at_3_score": round(p_at_3, 2),
            "retrieved_context": formatted_results
        })
        
    avg_precision = total_precision / len(eval_dataset)
    md_table_rows.extend([
        "",
        f"**Average System Precision:** {avg_precision:.2f}"
    ])
    
    print("\n" + "="*60)
    print(f"✅ EVALUATION COMPLETE | Average System Precision: {avg_precision:.2f}")
    print("="*60)

    # Save files to the same folder as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    md_filepath = os.path.join(script_dir, "evaluation_results.md")
    json_filepath = os.path.join(script_dir, "retrieved_results.json")
    
    with open(md_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(md_table_rows))
        
    with open(json_filepath, "w", encoding="utf-8") as f:
        json.dump(json_export_data, f, indent=4, ensure_ascii=False)
        
    print(f"\n📁 Exported Markdown Table to: {md_filepath}")
    print(f"📁 Exported Retrieved JSON to: {json_filepath}\n")

if __name__ == "__main__":
    evaluate_retrieval()