from pathlib import Path
from .db import Database

def export_to_vault(database: Database, vault_path: str = "MindWeave_Vault"):
    vault_dir = Path(vault_path)
    vault_dir.mkdir(parents=True, exist_ok=True)
    
    items = database.all_knowledge()
    relationships = database.relationships()
    
    for item in items:
        filename = "".join(c for c in item["concept"] if c.isalnum() or c in " -_").strip() + ".md"
        filepath = vault_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(f"topic: {item['topic']}\n")
            f.write(f"version: {item['version']}\n")
            f.write(f"confidence: {item['confidence']}\n")
            f.write("---\n\n")
            f.write(f"# {item['concept']}\n\n")
            f.write(f"{item['explanation']}\n\n")
            
            item_rels = [r for r in relationships if r['from_knowledge_id'] == item['id']]
            if item_rels:
                f.write("## Related Concepts\n")
                for r in item_rels:
                    f.write(f"- **{r['relation_type'].replace('_', ' ').title()}**: [[{r['to_concept']}]]\n")
