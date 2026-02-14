# IT Service Desk Sentiment Analysis 

## Estructura del Proyecto
```text
tfg-it-support-ia/
├── data/                       # Datos originales y procesados (Ignorados por Git)
│   ├── raw/                    # CSVs y XLSX originales de Mendeley
│   └── processed/              # Dataset final unificado
├── notebooks/                  # Jupyter Notebooks de experimentación
│   ├── 01_data_cleaning.ipynb
│   ├── 02_eda_analysis.ipynb
│   └── 03_ia_validation.ipynb
├── src/                        # Código fuente modular (.py)
│   ├── data_loader.py
│   ├── classifier.py
│   └── utils.py
├── docs/                       # Actas y documentación
├── .env                        # API Keys (Privado)
├── .gitignore                  # Configuración de archivos excluidos
├── requirements.txt            # Dependencias del proyecto
└── README.md                   # Documentación principal


---

## 📊 Descripción del Dataset

El proyecto utiliza el dataset **"Help Desk Tickets"**, una base de datos de alta fidelidad que documenta el ciclo de vida completo de las incidencias en un entorno corporativo de soporte técnico.

### 1. Fuente y Origen

* **Fuente:** Mendeley Data (Repositorio de datos científicos de Elsevier).
* **Autor:** Mohammad Abdellatif.
* **Fecha de Publicación:** 30 de mayo de 2025 (Versión 2).
* **Institución:** Princess Sumaya University for Technology.
* **Contexto:** Los datos fueron extraídos de una **empresa internacional de software** real, cubriendo tickets reportados entre enero de 2016 y marzo de 2023.

### 2. Composición del Dataset

El dataset no es un archivo único, sino un ecosistema de archivos interconectados que permiten una validación cruzada:

* **`issues.csv` (19.6 MB):** Contiene la información estructural de miles de tickets (categoría, prioridad, proyecto, tiempos de resolución).
* **`sample_utterances.csv` (3.22 MB):** Es el **núcleo de nuestro análisis de IA**. Contiene los mensajes de texto (comentarios) intercambiados entre los usuarios (`reporter`) y los técnicos (`assignee`).
* **`issues_snapshot_sample.xlsx` (103 KB):** Es una muestra "maestra" evaluada manualmente por un **manager de Help Desk**, lo que nos proporciona un *Ground Truth* (verdad absoluta) sobre el rendimiento y la naturaleza de los tickets.

### 3. Relevancia para el TFG (Por qué este y no otro)

Este dataset ha sido elegido por encima de opciones comunes en Kaggle por cuatro motivos críticos:

1. **Dualidad Datos/Texto:** Permite entrenar modelos de Machine Learning clásico con datos numéricos (tiempos de resolución) y modelos de IA (LLMs) con el texto de los mensajes.
2. **Validación Humana:** Al incluir valoraciones de un manager real, podemos medir si la IA coincide con el juicio de un experto humano.
3. **Realismo B2B:** El texto incluye jerga técnica profesional, frustraciones de clientes corporativos y reincidencias, evitando el sesgo de "datasets de juguete" o plantillas repetitivas.
4. **Cumplimiento de Objetivos:** Facilita directamente el análisis de **Sentimiento Negativo** y la **Priorización de Urgencia** que exige el Acta 1 del proyecto.

