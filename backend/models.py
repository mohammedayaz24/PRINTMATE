from sqlalchemy import Column, Integer, String, Enum
from backend.database import Base
import enum

class UserRole(str, enum.Enum):
    student = "student"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    rollno = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(15), nullable=True)
    role = Column(Enum(UserRole), nullable=False)
