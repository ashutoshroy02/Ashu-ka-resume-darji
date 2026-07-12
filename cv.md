# ASHUTOSH ROY
AI/ML Engineer | Deep Learning Researcher | AI Agents & GenAI | Full Stack Developer
**Location:** Gurugram, Haryana
**Contact:** +91-9810599837 | ashu2003roy@gmail.com
**Links:** [Portfolio](https://mitovoid.netlify.app/) | [GitHub](https://github.com/ashutoshroy02) | [LinkedIn](https://linkedin.com/in/ashutosh-roy-02)

---

## SUMMARY
Versatile AI/ML Engineer, Deep Learning Researcher, and Full Stack Developer with 1+ year of hands-on experience building scalable AI systems, autonomous AI agents, RAG pipelines, and production-ready web applications. Published researcher (RECCAP 2026, IIT Palakkad — first author; co-author, IIT Delhi) with expertise in fine-tuning LLMs (QLoRA/LoRA), hybrid retrieval systems, speech/affective computing, and multi-agent orchestration (LangGraph, MCP). Proficient in Python, PyTorch, FastAPI, React/Next.js, and LangChain — focused on shipping low-latency, production-grade AI and full-stack products end-to-end.

---

## EXPERIENCE

**Research Intern** | Indian Institute of Technology (IIT) Delhi, New Delhi | *Jan 2025 – Jun 2025*
- Built OCR-powered document understanding pipelines (Tesseract, Marker, Gemini OCR, Surya OCR), benchmarking engines across document classes on 10,000+ archaeological records to optimize extraction accuracy (+22%).
- Designed hybrid retrieval pipelines (FAISS/Pinecone dense + Apache Solr sparse), improving semantic + lexical search accuracy by 35% across historical/archaeological archives.
- Built and deployed scalable FastAPI REST APIs for real-time LLM inference and document retrieval, reducing latency by 35% and supporting 1,000+ daily search requests with sub-second multi-modal response.
- Also delivered the frontend layer (React, Next.js) for the AI-powered archive search platform, improving researcher-facing UX.
- Co-authored **SARCH: Multimodal Search for Archaeological Archives** with IIT Delhi (Prof. Maya Ramanath) — submitted for peer review. [arxiv.org/abs/2511.05667](https://arxiv.org/abs/2511.05667)

**AI/ML Engineer Intern** | MitoVoid AI, Remote | *Oct 2024 – Nov 2024*
- Fine-tuned transformer-based models (Mistral 7B / LLaMA) via QLoRA (4-bit quantization) for healthcare, building conversational AI agents for medical record summarization and symptom-based analysis.
- Built end-to-end Python ML pipelines (ingestion → preprocessing → inference → deployment) with OCR modules to extract structured text from medical reports.
- Integrated autonomous tool-calling and deployed a FastAPI chatbot backend, cutting patient query resolution time by ~40% through optimized intent routing.
- Also built the product's healthcare-facing frontend (React, Next.js, TypeScript, Tailwind CSS) — reusable UI components, authentication, and third-party/API integrations — and deployed via Git, Docker, and Vercel.
- Optimized inference latency by 30% through batch processing and model quantization.

**Software Engineer Intern** | LeanTactics Solutions Pvt. Ltd., Remote | *Nov 2024 – Dec 2024*
- Engineered and deployed high-performance backend services (Python, FastAPI) enabling scalable AI-driven applications with consistent low-latency responses.
- Integrated ML model inference outputs into production backend systems, optimizing data flow between inference layers and the application.
- Profiled API performance bottlenecks using data-driven approaches, achieving a 25–35% reduction in response latency under production load.

---

## PUBLICATIONS & RESEARCH

**Multitask Speech Emotion & Stress Detection (Wav2Vec2–BiLSTM)** — *First author* | Accepted, RECCAP 2026, IIT Palakkad (IEEE) | *2026*
- Proposed a self-supervised Wav2Vec2 + BiLSTM multitask architecture for simultaneous 5-class emotion classification and continuous stress regression.
- Evaluated across 3 corpora (RAVDESS, TESS, SAVEE) with a unified preprocessing pipeline (VAD, silence removal, log-Mel spectrograms) and data augmentation.
- Achieved **85.9% accuracy, 0.856 F1-score, 0.1268 RMSE**, outperforming baseline models.
- Co-authored with Sejal Sahu and Dr. Toran Verma (Paper ID 723); presented at IIT Palakkad, May 2026.

**SARCH: Multimodal Search for Archaeological Archives** — *Co-author, with IIT Delhi* | *Nov 2025*
- Proposed a multimodal retrieval system combining OCR (Surya), image classification, and hybrid search (FAISS + Apache Solr) for large-scale scanned archaeological archives.
- Benchmarked multiple OCR engines (Tesseract, Marker, Gemini OCR) across diverse historical document layouts. [arxiv.org/abs/2511.05667](https://arxiv.org/abs/2511.05667)

---

## PROJECTS

**[Archaeological Full-Stack Search Engine](https://github.com/ashutoshroy02/IITDTIE)** | Python, Surya OCR, Apache Solr, FAISS, FastAPI, C++, NLP | *Jan 2025 – Jun 2025*
- Built an end-to-end search engine for archaeological archives at IIT Delhi, processing scanned manuscripts, books, maps, and historical records.
- Implemented metadata extraction and semantic indexing (Apache Solr + FAISS), enabling sub-second keyword and vector-based retrieval across multimodal (text + image) content.

**[Shopping Assistant Agent](https://github.com/ashutoshroy02/shopping-assistant-agent-)** | Python, LangGraph, MCP, Claude 3.5, FastAPI | *Feb 2026 – May 2026*
- Engineered a multi-agent shopping assistant using LangGraph to coordinate specialized agents for product search, comparison, recommendation, and review summarization with self-reflection loops.
- Developed custom MCP servers for secure, real-time tool calling with product APIs and shopping databases — reducing response time by 35% and improving recommendation quality.

**[Skills-for-Agents Framework](https://github.com/ashutoshroy02/skills-for-agents)** | Python, LangGraph, MCP, AI Agents, Open Source | *Apr 2026 – May 2026*
- Built an open-source, production-ready ecosystem of composable, conflict-free instruction sets for multi-task LLM agents — each skill owns exactly one domain (voice, density, craft, process, content).
- Designed the **Skills Interoperability Protocol (SIP)**, reducing prompt duplication by 60% and preventing instruction conflicts during concurrent multi-agent execution.

**[Speech Emotion & Stress Detection](https://github.com/ashutoshroy02/EchoEmotion)** | PyTorch, Wav2Vec2, BiLSTM, Hugging Face, Python | *Jan 2026 – May 2026* — RECCAP 2026
- Built a self-supervised Wav2Vec2 + BiLSTM multitask architecture across 3 corpora (RAVDESS, TESS, SAVEE) for simultaneous emotion classification and stress regression.
- Achieved 85.9% accuracy, 0.856 F1-score, 0.1268 RMSE through unified preprocessing and hyperparameter tuning; research accepted at RECCAP 2026 (IEEE).
- *(Core ML training repo: [emotion-stress-ml](https://github.com/ashutoshroy02/emotion-stress-ml))*

**[Exam-Helper Agentic RAG System](https://github.com/ashutoshroy02/Exam-Helper)** | Python, LLaMA 3, LangGraph, LangChain, FAISS, Pinecone, FastAPI, Streamlit | *Dec 2024 – Apr 2025*
- Built an LLM-powered autonomous contextual QA agent (LLaMA 3 via LangGraph/LangChain) with multimodal ingestion (PDFs, images, YouTube transcripts).
- Implemented dense hybrid retrieval (FAISS + Pinecone) with semantic chunking, reducing hallucinations by ~40% and improving answer accuracy through dynamic context retrieval.

**Resumora — AI Resume Builder** | Next.js, React, FastAPI, PostgreSQL, Astro | *Apr 2026 – Present*
- Building a full-stack AI resume builder for resume creation, cover letters, and job-application tracking.
- Integrated LLMs to generate ATS-friendly resumes, tailor content to job descriptions, and auto-generate personalized cover letters.
- Implemented bulk email automation with personalized templates, campaign tracking, and one-click job-application workflows.

**[InterviewPrep](https://github.com/ashutoshroy02/InterviewPrep)** | Next.js, React, TypeScript, Tailwind CSS, Firebase, Astro | *May 2026 – Jun 2026*
- Built and open-sourced a full-stack interview prep platform with 700+ curated technical/behavioral questions, company-specific tracks (FAANG, OpenAI, NVIDIA, Indian IT), a 12-week roadmap, and interactive flashcards.
- Implemented Firebase Authentication and responsive React UI; optimized SEO via static generation and schema markup, achieving a **95+ Lighthouse score**.

**Industrial Defect Detection & Quality Inspection System** | YOLOv8, PyTorch, OpenCV, CUDA, Python | *Feb 2025 – Apr 2025*
- Built a real-time computer vision system for automated manufacturing quality inspection, fine-tuning YOLOv8 on custom-annotated datasets across 4 defect types (scratches, dents, cracks, missing components).
- Implemented image augmentation pipelines for robustness under varying factory lighting/camera conditions, with GPU-accelerated low-latency inference.
- *(Repo: [Industrial-Defect-Detection-System](https://github.com/ashutoshroy02/Industrial-Defect-Detection-System))*

**[Medical Chatbot & LLM Fine-Tuning](https://github.com/ashutoshroy02/Medical-chatbot)** | Mistral 7B, QLoRA, Transformers, Tesseract OCR, Python | *Mar 2024 – Apr 2024*
- Fine-tuned Mistral 7B using QLoRA (4-bit quantization) for healthcare-focused conversational AI, reducing GPU memory usage by ~75% while maintaining performance.
- Built an OCR + OpenCV preprocessing pipeline to extract structured data from 1,000+ unstructured medical reports and prescriptions.

**[Music Identification App (BeatBubble)](https://github.com/ashutoshroy02/Beat-Bubble)** | Streamlit, Python, Flutter, Firebase, ACRCloud API | *Jun 2024 – Dec 2024*
- Built a cross-platform, real-time audio recognition pipeline (microphone capture → feature extraction → ACRCloud fingerprinting → metadata retrieval).
- Integrated Firebase Authentication and deployed responsive Streamlit + Flutter UIs for instant song identification and personalized search history.

**URL Shortener (Chota-link)** | Python, FastAPI, PostgreSQL, Redis, Docker | *2026*
- Built a scalable URL shortener with REST APIs, custom short links, and analytics; integrated Redis caching, reducing response time by 40%.
- *(Repo: [Chota-link](https://github.com/ashutoshroy02/Chota-link))*

**Netflix Data Analysis** | Python, Pandas, NumPy, Matplotlib, Seaborn, Jupyter | *Jun 2026*
- Cleaned and analyzed data from 8,000+ Netflix titles; built visualizations identifying trends in genres, ratings, countries, and release years to support data-driven insights.
- *(Repo: [Netflix-Data-Analysis](https://github.com/ashutoshroy02/Netflix-Data-Analysis))*

**[BulkyMail](https://github.com/ashutoshroy02/BULK-MAIL)** | Python, Streamlit, SMTP/API | *Dec 2024*
- Built a Streamlit-based bulk email automation app with dynamic Jinja2 templating, processing structured CSVs for personalized outreach at scale (100+ emails/run); contributed to successful internship conversions for multiple users.

---

## TECHNICAL SKILLS

- **AI/ML & Research:** LLMs, GenAI, RAG, AI Agents (LangGraph, MCP, Agentic AI), Transformer Fine-Tuning (QLoRA/LoRA), Self-Supervised Learning, Deep Learning, NLP, Multimodal AI, Speech/Audio Processing, Computer Vision (YOLOv8, OpenCV, OCR), Dense Retrieval, Prompt Engineering, Function/Tool Calling
- **Frontend:** React.js, Next.js, Astro, TypeScript, JavaScript (ES6+), HTML5, CSS3, Tailwind CSS, Responsive Design
- **Backend & APIs:** Python, FastAPI, Node.js, Express.js, REST API Design, Authentication (JWT/OAuth), Streamlit
- **Libraries & Frameworks:** PyTorch, TensorFlow, Hugging Face Transformers, LangChain, LangGraph, Scikit-learn, Pandas, NumPy, OpenCV
- **Databases & Vector Stores:** FAISS, Pinecone, Apache Solr, PostgreSQL, MySQL, MongoDB, Firebase, Supabase, Redis
- **Data Science:** EDA, Statistical Analysis, Feature Engineering, Regression, Classification, Clustering, Time Series, Power BI, Tableau
- **Languages:** Python, C++, SQL, JavaScript
- **Cloud, Tools & DevOps:** Git, GitHub Actions (CI/CD), Docker, Linux, Vercel, Netlify, AWS (EC2, S3), Jupyter, Google Colab, Postman

---

## ACHIEVEMENTS
- Published 2 research papers — first-author acceptance at RECCAP 2026 (IEEE) and co-authored work with IIT Delhi.
- Solved 150+ DSA problems on LeetCode, strengthening data structures and algorithms fundamentals.
- Won 2 AI/ML Hackathons, building functional AI solutions under time constraints.
- Active open-source contributor across AI/ML projects on GitHub and Hugging Face.
- Certifications in Machine Learning, Deep Learning, Generative AI, NLP, and Python.

---

## EDUCATION

**Chhattisgarh Swami Vivekananda Technical University (CSVTU)**, Bhilai | *2022 – 2026*
- B.Tech (Hons) in Computer Science and Engineering (Artificial Intelligence)
- Relevant Coursework: Deep Learning, NLP, Computer Vision, Data Structures & Algorithms

**St. Columbus School**, Faridabad | *2020 – 2021*
- Higher Secondary (Class XII – Science, PCMB) — 87%
- Secondary Education (Class X) — 93.8%