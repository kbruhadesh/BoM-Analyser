from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class BomTask(Base):
    __tablename__ = "bom_tasks"

    id = Column(String, primary_key=True)          # UUID4
    status = Column(String, default="pending")      # pending|processing|complete|failed
    progress = Column(Integer, default=0)           # 0-100
    current_component = Column(String, nullable=True)
    raw_input = Column(Text)
    input_format = Column(String)                   # csv|text|xlsx_base64
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    items = relationship("BomItem", back_populates="task", cascade="all, delete-orphan")
    results = relationship("OptimizedResult", back_populates="task", cascade="all, delete-orphan")


class BomItem(Base):
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("bom_tasks.id"))
    line_number = Column(Integer)
    quantity = Column(Integer)
    raw_description = Column(String)
    manufacturer_part_number = Column(String, nullable=True)
    normalized_mpn = Column(String, nullable=True)
    normalization_confidence = Column(Float, nullable=True)
    manufacturer = Column(String, nullable=True)
    reference_designators = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    task = relationship("BomTask", back_populates="items")
    vendor_results = relationship("VendorResult", back_populates="bom_item", cascade="all, delete-orphan")


class VendorResult(Base):
    __tablename__ = "vendor_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_item_id = Column(Integer, ForeignKey("bom_items.id"))
    vendor = Column(String)                         # DigiKey|Mouser|Arrow|LCSC|Robu|Evelta
    vendor_part_number = Column(String)
    unit_price_inr = Column(Float)                  # Price in Indian Rupees
    unit_price_usd = Column(Float, nullable=True)   # Original USD if converted
    price_breaks_json = Column(JSON)                # [{"qty": 1, "price_inr": 95.0}]
    stock_qty = Column(Integer)
    availability = Column(String)                   # In Stock|Out of Stock|On Order
    moq = Column(Integer, default=1)
    lead_time_weeks = Column(Integer, nullable=True)
    datasheet_url = Column(String, nullable=True)
    cache_hit = Column(Boolean, default=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    bom_item = relationship("BomItem", back_populates="vendor_results")


class OptimizedResult(Base):
    __tablename__ = "optimized_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("bom_tasks.id"))
    component = Column(String)
    normalized_mpn = Column(String)
    quantity_required = Column(Integer)
    best_vendor = Column(String, nullable=True)
    best_unit_price_inr = Column(Float, nullable=True)
    best_total_price_inr = Column(Float, nullable=True)
    availability = Column(String)
    moq = Column(Integer, nullable=True)
    alternatives_json = Column(JSON, default=list)
    savings_vs_worst_inr = Column(Float, default=0.0)
    recommendation_reason = Column(String, nullable=True)
    all_vendors_json = Column(JSON, default=list)

    task = relationship("BomTask", back_populates="results")


class ScrapeAuditLog(Base):
    __tablename__ = "scrape_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=True)
    vendor = Column(String)
    url = Column(String)
    mpn = Column(String)
    response_status = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, default=False)
    error = Column(String, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)


def get_engine(database_url: str = "sqlite:///./bom.db"):
    return create_engine(database_url, connect_args={"check_same_thread": False})


def get_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(database_url: str = "sqlite:///./bom.db"):
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return engine
