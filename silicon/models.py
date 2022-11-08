from sqlalchemy import Column, DateTime, JSON, Integer, String, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SafetyDataSheet(Base):
    __tablename__ = "safety_data_sheets"
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    product_name = Column(String, nullable=False)
    product_number = Column(String, nullable=False)
    cas_number = Column(String, nullable=False)
    pdf_download_url = Column(String, nullable=False)
    data = Column(JSON, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
