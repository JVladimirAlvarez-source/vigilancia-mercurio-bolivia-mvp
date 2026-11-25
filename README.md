# Vigilancia Inteligente de Intoxicación por Mercurio — Bolivia (MVP)

Prototipo de soporte a la decisión clínica y epidemiológica alineado con la **Guía Técnica N.º 537 (Ministerio de Salud y Deportes de Bolivia, 2024)**.

## Ejecución Rápida
```bash
pip install -r requirements.txt
python src/generate_synthetic_bolivia.py --out ./data
python src/train_models.py
streamlit run app/app.py
