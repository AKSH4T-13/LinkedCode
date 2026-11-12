from backend.database import engine, Base
from backend.models import User, SolvedQuestion, RecommendationHistory

Base.metadata.create_all(bind=engine)

print("LinkedCode database initialized successfully!")