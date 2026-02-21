from sqlalchemy import Column, Integer, String, ForeignKey
from .base import Base

class WardDeptOfficer(Base):
    __tablename__ = "ward_dept_officers"
    ward_id = Column(Integer, primary_key=True)
    dept_id = Column(String(5), ForeignKey("departments.dept_id"), primary_key=True)
    officer_id = Column(Integer, ForeignKey("users.id"))
