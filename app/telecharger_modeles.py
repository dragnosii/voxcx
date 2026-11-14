"""Télécharge les modèles locaux dans app/models (une seule fois, ensuite tout fonctionne hors ligne)."""
import os
from huggingface_hub import snapshot_download

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODELES = {
    # sentiment multilingue (négatif / neutre / positif), dont français, anglais, arabe, espagnol, italien
    "cardiffnlp/twitter-xlm-roberta-base-sentiment": "sentiment",
    # embeddings multilingues (thèmes, recherche d'avis pour l'assistant)
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": "embeddings",
}
for repo, nom in MODELES.items():
    print("Téléchargement :", repo, flush=True)
    snapshot_download(
        repo_id=repo,
        local_dir=os.path.join(DOSSIER, nom),
        allow_patterns=["*.json", "*.txt", "*.model", "*.safetensors", "pytorch_model.bin", "1_Pooling/*", "modules.json"],
        ignore_patterns=["*onnx*", "*openvino*", "tf_model*", "flax_model*"],
    )
    print("   terminé :", nom, flush=True)
print("Tous les modèles sont téléchargés.")
