from backend.llm.token_budget import LLMBudgetExceeded
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import Base, engine, SessionLocal
import backend.models

from backend.services.question_analyzer import analyze_questions
from backend.services.leetcode_service import fetch_recent_questions

from backend.graph.workflow import linkedcode_graph
from backend.agents.question_generator import SolutionAuditFailure
from backend.core.dependencies import get_current_user

from backend.models import User, GeneratedQuestion

from backend.routers.auth import router as auth_router
from backend.routers.practice import router as practice_router
from backend.routers.execution import router as execution_router


# =========================================================
# LOGGING CONFIGURATION
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

Base.metadata.create_all(bind=engine)
print("DATABASE:", engine.url)
print("REGISTERED TABLES:", Base.metadata.tables.keys())
app = FastAPI(
    title="LinkedCode API",
    description="AI-powered personalized DSA practice platform",
    version="1.0.0"
)


# =========================================================
# CORS CONFIGURATION
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# =========================================================
# ROUTER REGISTRATION
# =========================================================

app.include_router(auth_router)
app.include_router(practice_router)
app.include_router(execution_router)
app.mount("/app", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True), name="frontend")


# =========================================================
# HOME ROUTE
# =========================================================

@app.get("/")
def home():

    return {
        "message": "LinkedCode Backend Running!"
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# =========================================================
# GET RECENT LEETCODE QUESTIONS
# =========================================================

@app.get("/leetcode/recent")
async def get_recent_questions(
    current_user: User = Depends(get_current_user)
):

    if not current_user.leetcode_username:
        raise HTTPException(
            status_code=400,
            detail="Please link your LeetCode account first."
        )

    try:
        result = await fetch_recent_questions(
            current_user.leetcode_username
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception:
        logger.exception("Failed to fetch LeetCode submissions.")

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch LeetCode submissions."
        )


# =========================================================
# ANALYZE LEETCODE PROFILE
# =========================================================

@app.get("/leetcode/analyze")
async def analyze_user_questions(
    current_user: User = Depends(get_current_user)
):

    if not current_user.leetcode_username:
        raise HTTPException(
            status_code=400,
            detail="Please link your LeetCode account first."
        )

    try:
        result = await analyze_questions(
            current_user.leetcode_username
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception:
        logger.exception("Unable to analyze LeetCode profile.")

        raise HTTPException(
            status_code=500,
            detail="Unable to analyze LeetCode profile."
        )


# =========================================================
# GENERATE PERSONALIZED RECOMMENDATIONS
# =========================================================

@app.post("/recommendations/generate")
async def generate_recommendations(
    current_user: User = Depends(get_current_user)
):

    if not current_user.leetcode_username:
        raise HTTPException(
            status_code=400,
            detail="Please link your LeetCode account first."
        )

    try:
        logger.info(
            "Starting recommendation workflow | User ID: %s | Username: %s",
            current_user.id,
            current_user.leetcode_username
        )

        initial_state = {
            "user_id": current_user.id,
            "username": current_user.leetcode_username,
            "errors": []
        }

        result = await linkedcode_graph.ainvoke(initial_state)

        logger.info(
            "Recommendation workflow completed | User ID: %s",
            current_user.id
        )

        return {
            "success": True,
            "user_id": current_user.id,
            "username": current_user.leetcode_username,
            "recommendations": result["final_recommendations"]
        }

    except LLMBudgetExceeded as error:
        logger.exception("Groq request budget exceeded | User ID: %s", current_user.id)
        raise HTTPException(status_code=503, detail=str(error))
    except SolutionAuditFailure:
        logger.exception("No audited draft could be produced | User ID: %s", current_user.id)
        raise HTTPException(
            status_code=502,
            detail="We could not validate an original problem after correction and a fresh draft. No question was saved. Please try again later."
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception:
        logger.exception(
            "Recommendation workflow failed | User ID: %s",
            current_user.id
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to generate recommendations."
        )


# =========================================================
# GET SAVED GENERATED QUESTIONS
# =========================================================

@app.get("/generated-questions")
def get_generated_questions(
    current_user: User = Depends(get_current_user)
):

    db = SessionLocal()

    try:
        questions = db.query(GeneratedQuestion).filter(
            GeneratedQuestion.user_id == current_user.id
        ).order_by(
            GeneratedQuestion.created_at.desc()
        ).all()

        return {
            "success": True,
            "total": len(questions),
            "questions": [
                {
                    "id": question.id,
                    "title": question.title,
                    "difficulty": question.difficulty,
                    "topics": question.topics,
                    "question_data": question.question_data,
                    "validation_report": question.validation_report,
                    "created_at": (
                        question.created_at.isoformat()
                        if question.created_at else None
                    )
                }
                for question in questions
            ]
        }

    except Exception:
        logger.exception(
            "Failed to retrieve generated questions | User ID: %s",
            current_user.id
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve generated questions."
        )

    finally:
        db.close()
