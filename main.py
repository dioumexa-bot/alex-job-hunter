"""
Alex Job Hunter - Backend API
Assistente inteligente para busca de vagas de emprego.
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

APP_VERSION = "1.0.0"

STORAGE_FILE = "applications.json"

ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRY = "br"

app = FastAPI(
    title="Alex Job Hunter",
    description="Assistente inteligente para busca de vagas de emprego",
    version=APP_VERSION,
)

KNOWN_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "SQL", "NoSQL", "React", "Vue",
    "Angular", "Node.js", "Django", "Flask", "FastAPI", "Spring", "AWS",
    "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "CI/CD", "Git",
    "Linux", "PostgreSQL", "MySQL", "MongoDB", "Redis", "GraphQL", "REST",
    "Machine Learning", "Data Science", "Pandas", "TensorFlow", "PyTorch",
    "Excel", "Power BI", "Tableau", "Scrum", "Agile", "Product Management",
    "UX Design", "UI Design", "Figma", "Marketing Digital", "SEO", "Vendas",
    "Gestão de Projetos", "Liderança", "Comunicação", "Inglês", "Espanhol",
]

SENIORITY_LEVELS = [
    (0, 2, "Júnior"),
    (2, 5, "Pleno"),
    (5, 9, "Sênior"),
    (9, 999, "Especialista/Staff"),
]

MOCK_COMPANIES = [
    "Nimbus Tech", "Orbita Digital", "Vortex Solutions", "Bluepeak Software",
    "Cedro Sistemas", "Fluxo Data", "Horizonte Cloud", "Lumen Labs",
    "Cascata Consulting", "Prisma Analytics",
]

MOCK_LOCATIONS = ["São Paulo, SP", "Rio de Janeiro, RJ", "Belo Horizonte, MG", "Curitiba, PR", "Remoto"]


class ResumeRequest(BaseModel):
    resume_text: str


class CandidateProfile(BaseModel):
    skills: List[str] = []
    years_experience: float = 0


class JobSearchRequest(BaseModel):
    candidate_profile: CandidateProfile
    keywords: List[str]
    location: Optional[str] = None
    remote: bool = False
    top_n: int = 5


class InterviewRequest(BaseModel):
    job_info: dict
    candidate_info: dict


class CoverLetterRequest(BaseModel):
    candidate_info: dict
    job_info: dict


class SaveApplicationRequest(BaseModel):
    job_info: dict
    candidate_info: Optional[dict] = None
    match_score: Optional[int] = None
    resume: Optional[str] = None
    cover_letter: Optional[str] = None
    recruiter_message: Optional[str] = None
    notes: Optional[str] = None


def extract_skills(text: str) -> List[str]:
    found = []
    lowered = text.lower()
    for skill in KNOWN_SKILLS:
        if skill.lower() in lowered:
            found.append(skill)
    return found


def estimate_years_experience(text: str) -> float:
    patterns = [
        r"(\d+(?:[.,]\d+)?)\s*\+?\s*anos? de experi[êe]ncia",
        r"(\d+(?:[.,]\d+)?)\s*\+?\s*years? of experience",
        r"(\d+(?:[.,]\d+)?)\s*\+?\s*anos?\b",
        r"(\d+(?:[.,]\d+)?)\s*\+?\s*years?\b",
    ]
    best = 0.0
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = float(match.group(1).replace(",", "."))
            best = max(best, value)
    return best


def seniority_for(years: float) -> str:
    for low, high, label in SENIORITY_LEVELS:
        if low <= years < high:
            return label
    return "Não identificado"


def build_resume_profile(resume_text: str) -> dict:
    skills = extract_skills(resume_text)
    years = estimate_years_experience(resume_text)
    return {
        "skills": skills,
        "years_experience": years,
        "seniority": seniority_for(years),
        "summary": (
            f"Perfil com {len(skills)} habilidade(s) identificada(s) e "
            f"aproximadamente {years:g} ano(s) de experiência "
            f"({seniority_for(years)})."
        ),
    }


def score_job_match(candidate_skills: List[str], job_skills: List[str], candidate_years: float, min_years: float) -> dict:
    casing_map = {s.lower(): s for s in candidate_skills}
    candidate_set = set(casing_map.keys())
    job_set = {s.lower() for s in job_skills}
    matched = sorted(job_set & candidate_set)
    skill_score = len(matched) / len(job_set) if job_set else 0.0
    experience_score = 1.0 if candidate_years >= min_years else max(0.0, candidate_years / max(min_years, 1))
    match_score = round((0.7 * skill_score + 0.3 * experience_score) * 100)
    return {
        "match_score": match_score,
        "matched_skills": [casing_map[s] for s in matched],
    }


def adzuna_configured() -> bool:
    return bool(ADZUNA_APP_ID and ADZUNA_APP_KEY)


def search_adzuna_jobs(request: JobSearchRequest) -> List[dict]:
    query = " ".join(request.keywords)
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": min(max(request.top_n * 2, 5), 50),
        "what": query,
        "content-type": "application/json",
    }
    if request.location:
        params["where"] = request.location

    url = f"https://api.adzuna.com/v1/api/jobs/{ADZUNA_COUNTRY}/search/1"

    try:
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        results = response.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []

    jobs = []
    for item in results:
        description = item.get("description", "") or ""
        title = item.get("title", "Vaga sem título")
        company = (item.get("company") or {}).get("display_name", "Empresa não informada")
        location = (item.get("location") or {}).get("display_name", request.location or "Brasil")
        is_remote = request.remote or "remoto" in description.lower() or "remote" in description.lower()

        if request.remote and not is_remote:
            continue

        job_skills = extract_skills(description) or request.candidate_profile.skills[:3]
        min_years = 0
        scoring = score_job_match(request.candidate_profile.skills, job_skills, request.candidate_profile.years_experience, min_years)

        jobs.append({
            "title": title,
            "company": company,
            "location": "Remoto" if is_remote else location,
            "remote": is_remote,
            "min_years_experience": min_years,
            "required_skills": job_skills,
            "url": item.get("redirect_url"),
            "source": "Adzuna",
            **scoring,
        })

    jobs.sort(key=lambda j: j["match_score"], reverse=True)
    return jobs[: request.top_n]


def generate_job_matches(request: JobSearchRequest) -> List[dict]:
    jobs = []
    for i in range(max(request.top_n, 1) * 2):
        keyword = request.keywords[i % len(request.keywords)]
        company = MOCK_COMPANIES[i % len(MOCK_COMPANIES)]
        location = request.location or MOCK_LOCATIONS[i % len(MOCK_LOCATIONS)]
        is_remote = request.remote or (i % 3 == 0)
        min_years = max(0, round(request.candidate_profile.years_experience) - 1 + (i % 3))
        job_skill_pool = request.candidate_profile.skills[: max(1, len(request.candidate_profile.skills) - i % 3)]
        extra_pool = [s for s in KNOWN_SKILLS if s not in job_skill_pool][i % 5: i % 5 + 2]
        job_skills = job_skill_pool + extra_pool

        scoring = score_job_match(request.candidate_profile.skills, job_skills, request.candidate_profile.years_experience, min_years)

        jobs.append({
            "title": f"{keyword.title()}",
            "company": company,
            "location": "Remoto" if is_remote else location,
            "remote": is_remote,
            "min_years_experience": min_years,
            "required_skills": job_skills,
            **scoring,
        })

    jobs.sort(key=lambda j: j["match_score"], reverse=True)
    return jobs[: request.top_n]


def build_interview_preparation(job_info: dict, candidate_info: dict) -> dict:
    job_title = job_info.get("title", "a vaga")
    company = job_info.get("company", "a empresa")
    required_skills = [s.lower() for s in job_info.get("required_skills", job_info.get("skills", []))]
    candidate_skills = candidate_info.get("skills", [])
    candidate_skills_lower = [s.lower() for s in candidate_skills]

    skills_to_highlight = [s for s in candidate_skills if s.lower() in required_skills]
    skill_gaps = [s for s in job_info.get("required_skills", job_info.get("skills", [])) if s.lower() not in candidate_skills_lower]

    likely_questions = [
        f"Conte-me sobre sua experiência com {skills_to_highlight[0]}." if skills_to_highlight else "Conte-me sobre sua trajetória profissional.",
        f"Por que você quer trabalhar na {company}?",
        f"O que te atraiu para a vaga de {job_title}?",
        "Descreva um desafio técnico ou profissional que você resolveu recentemente.",
        "Onde você se vê daqui a 3 anos?",
    ]

    if skill_gaps:
        likely_questions.append(
            f"Como você lidaria com o fato de não ter experiência prévia em {skill_gaps[0]}?"
        )

    return {
        "job_title": job_title,
        "company": company,
        "skills_to_highlight": skills_to_highlight,
        "skill_gaps": skill_gaps,
        "likely_questions": likely_questions,
        "star_method_tip": (
            "Estruture suas respostas comportamentais usando o método STAR: "
            "Situação, Tarefa, Ação e Resultado. Foque em resultados mensuráveis."
        ),
        "questions_to_ask_interviewer": [
            "Como é o processo de onboarding e os primeiros 90 dias na função?",
            "Como o time mede sucesso nesta posição?",
            "Quais são os maiores desafios do time atualmente?",
        ],
    }


def generate_cover_letter_text(candidate_info: dict, job_info: dict) -> str:
    name = candidate_info.get("name", "Candidato(a)")
    years = candidate_info.get("years_experience", "")
    skills = candidate_info.get("skills", [])
    job_title = job_info.get("title", "a vaga")
    company = job_info.get("company", "a empresa")

    skills_text = ", ".join(skills[:5]) if skills else "as habilidades relevantes para a área"
    experience_text = f"com {years} anos de experiência " if years else ""

    letter = f"""Prezado(a) recrutador(a) da {company},

Escrevo para manifestar meu interesse na vaga de {job_title}. Sou um(a) profissional {experience_text}na área, com sólida experiência em {skills_text}, e acredito que meu perfil se alinha bem às necessidades do time.

Ao longo da minha trajetória, desenvolvi a capacidade de entregar resultados consistentes, colaborar em equipes multidisciplinares e me adaptar rapidamente a novos desafios. Fico entusiasmado(a) com a possibilidade de contribuir com a {company} e crescer profissionalmente junto ao time.

Agradeço a atenção e fico à disposição para conversarmos.

Atenciosamente,
{name}"""
    return letter


def generate_tailored_resume_text(candidate_info: dict, job_info: dict) -> str:
    name = candidate_info.get("name", "Candidato(a)")
    years = candidate_info.get("years_experience", 0)
    candidate_skills = candidate_info.get("skills", [])
    experience_entries = candidate_info.get("experience", [])
    education = candidate_info.get("education", [])
    contact = candidate_info.get("contact", "")

    job_title = job_info.get("title", "a vaga")
    company = job_info.get("company", "")
    required_skills = job_info.get("required_skills", job_info.get("skills", []))

    required_lower = [s.lower() for s in required_skills]
    matched = [s for s in candidate_skills if s.lower() in required_lower]
    other_skills = [s for s in candidate_skills if s.lower() not in required_lower]
    ordered_skills = matched + other_skills

    lines = []
    lines.append(name.upper())
    if contact:
        lines.append(contact)
    lines.append("")
    lines.append("OBJETIVO")
    target = f" na {company}" if company else ""
    lines.append(f"Atuar como {job_title}{target}, aplicando experiência de "
                  f"{years} ano(s) e habilidades em {', '.join(matched[:4]) if matched else ', '.join(ordered_skills[:4])}.")
    lines.append("")
    lines.append("RESUMO")
    if matched:
        lines.append(
            f"Profissional com {years} ano(s) de experiência, com forte alinhamento aos requisitos "
            f"da vaga em: {', '.join(matched)}. Pronto(a) para contribuir imediatamente com o time."
        )
    else:
        lines.append(
            f"Profissional com {years} ano(s) de experiência e histórico consistente de entrega de resultados, "
            f"buscando aplicar e expandir suas competências na área de {job_title}."
        )
    lines.append("")
    lines.append("HABILIDADES")
    lines.append(", ".join(ordered_skills) if ordered_skills else "—")
    if experience_entries:
        lines.append("")
        lines.append("EXPERIÊNCIA PROFISSIONAL")
        for entry in experience_entries:
            lines.append(f"• {entry}")
    if education:
        lines.append("")
        lines.append("FORMAÇÃO")
        for entry in education:
            lines.append(f"• {entry}")

    return "\n".join(lines)


def generate_recruiter_message_text(candidate_info: dict, job_info: dict) -> str:
    name = candidate_info.get("name", "")
    years = candidate_info.get("years_experience", "")
    skills = candidate_info.get("skills", [])
    job_title = job_info.get("title", "a vaga")
    company = job_info.get("company", "")

    required_skills = job_info.get("required_skills", job_info.get("skills", []))
    required_lower = [s.lower() for s in required_skills]
    matched = [s for s in skills if s.lower() in required_lower]
    highlight = matched[0] if matched else (skills[0] if skills else None)

    company_part = f" na {company}" if company else ""
    experience_part = f" Tenho {years} ano(s) de experiência" if years else " Tenho experiência"
    skill_part = f" em {highlight}" if highlight else " na área"

    message = (
        f"Olá{', ' + name if name else ''}! Vi a vaga de {job_title}{company_part} e fiquei bastante "
        f"interessado(a).{experience_part}{skill_part} e acredito que meu perfil combina bem com o que "
        f"vocês estão buscando. Ficaria feliz em conversar mais sobre a oportunidade — obrigado(a) pelo "
        f"tempo! 😊"
    )
    return message


def load_applications() -> List[dict]:
    if not os.path.exists(STORAGE_FILE):
        return []
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_application_record(record: dict) -> dict:
    applications = load_applications()
    applications.insert(0, record)
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(applications, f, ensure_ascii=False, indent=2)
    return record


def delete_application_record(app_id: str) -> bool:
    applications = load_applications()
    remaining = [a for a in applications if a.get("id") != app_id]
    if len(remaining) == len(applications):
        return False
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(remaining, f, ensure_ascii=False, indent=2)
    return True


@app.get("/")
def root():
    return {"message": "Alex Job Hunter API está no ar", "version": APP_VERSION}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/analyze-resume")
def analyze_resume(request: ResumeRequest):
    return {"profile": build_resume_profile(request.resume_text)}


@app.post("/find-jobs")
def find_jobs(request: JobSearchRequest):
    if adzuna_configured():
        real_matches = search_adzuna_jobs(request)
        if real_matches:
            return {"matches": real_matches, "source": "adzuna"}
    return {"matches": generate_job_matches(request), "source": "simulado"}


@app.post("/prepare-interview")
def prepare_interview(request: InterviewRequest):
    return {"preparation": build_interview_preparation(request.job_info, request.candidate_info)}


@app.post("/generate-cover-letter")
def generate_cover_letter(request: CoverLetterRequest):
    return {"cover_letter": generate_cover_letter_text(request.candidate_info, request.job_info)}


@app.post("/generate-resume")
def generate_resume(request: CoverLetterRequest):
    return {"resume": generate_tailored_resume_text(request.candidate_info, request.job_info)}


@app.post("/generate-recruiter-message")
def generate_recruiter_message(request: CoverLetterRequest):
    return {"message": generate_recruiter_message_text(request.candidate_info, request.job_info)}


@app.post("/applications")
def save_application(request: SaveApplicationRequest):
    record = request.dict()
    record["id"] = str(uuid.uuid4())
    record["saved_at"] = datetime.now(timezone.utc).isoformat()
    save_application_record(record)
    return {"application": record}


@app.get("/applications")
def list_applications():
    return {"applications": load_applications()}


@app.delete("/applications/{app_id}")
def delete_application(app_id: str):
    deleted = delete_application_record(app_id)
    return {"deleted": deleted}


@app.get("/api/health")
def api_health():
    return health()


@app.post("/api/analyze-resume")
def api_analyze_resume(request: ResumeRequest):
    return analyze_resume(request)


@app.post("/api/find-jobs")
def api_find_jobs(request: JobSearchRequest):
    return find_jobs(request)


@app.post("/api/prepare-interview")
def api_prepare_interview(request: InterviewRequest):
    return prepare_interview(request)


@app.post("/api/generate-cover-letter")
def api_generate_cover_letter(request: CoverLetterRequest):
    return generate_cover_letter(request)


@app.post("/api/generate-resume")
def api_generate_resume(request: CoverLetterRequest):
    return generate_resume(request)


@app.post("/api/generate-recruiter-message")
def api_generate_recruiter_message(request: CoverLetterRequest):
    return generate_recruiter_message(request)


@app.post("/api/applications")
def api_save_application(request: SaveApplicationRequest):
    return save_application(request)


@app.get("/api/applications")
def api_list_applications():
    return list_applications()


@app.delete("/api/applications/{app_id}")
def api_delete_application(app_id: str):
    return delete_application(app_id)


@app.get("/app")
def serve_frontend():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
