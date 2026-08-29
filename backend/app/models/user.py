from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Boolean, ARRAY, LargeBinary
from sqlalchemy.sql import func
from app.core.database import Base
from pgvector.sqlalchemy import Vector
import enum

class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    STAFF = "STAFF"
    SECURITY_ADMIN = "SECURITY_ADMIN"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone_number = Column(String(20))
    role = Column(Enum(UserRole), default=UserRole.STUDENT)
    karma_score = Column(Integer, default=100)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
