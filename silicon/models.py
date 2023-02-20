from sqlalchemy import (
    ARRAY,
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SafetyDataSheet(Base):
    __tablename__ = "safety_data_sheets"
    __table_args__ = (
        UniqueConstraint("product_name", "product_number", "product_brand", "cas_number"),
    )
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    product_name = Column(String, nullable=False)
    product_number = Column(String, nullable=False)
    product_brand = Column(String, nullable=False)
    cas_number = Column(String, nullable=False)
    hazards = Column(ARRAY(String), nullable=False, server_default=r"{}")
    pdf_download_url = Column(String, nullable=False)
    data = Column(JSON, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
