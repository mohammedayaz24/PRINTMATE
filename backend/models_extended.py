from sqlalchemy import Column, Integer, String, Enum, Text, DateTime
from backend.database import Base
import enum
from datetime import datetime

class UserRole(str, enum.Enum):
    student = "student"
    admin = "admin"

class OrderStatus(str, enum.Enum):
    Pending = "Pending"
    Printing = "Printing"
    Completed = "Completed"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    rollno = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(15), nullable=True)
    role = Column(Enum(UserRole), nullable=False)

class Order(Base):
    __tablename__ = "orders"

    id = Column(String(50), primary_key=True, index=True)
    rollno = Column(String(50), nullable=False)
    username = Column(String(50), nullable=False)
    fileName = Column(String(255), nullable=False)
    fileDataUrl = Column(Text, nullable=False)
    pageCount = Column(Integer, nullable=False)
    color = Column(String(20), nullable=False)
    fragment = Column(String(50), nullable=False)
    binding = Column(String(20), nullable=False)
    copies = Column(Integer, nullable=False)
    cost = Column(String(20), nullable=False)
    startPage = Column(Integer, nullable=False)
    endPage = Column(Integer, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.Pending)
    date = Column(DateTime, default=datetime.utcnow)
