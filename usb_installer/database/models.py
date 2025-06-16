from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Table, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

installation_assets = Table(
    "installation_assets",
    Base.metadata,
    Column("installation_id", Integer, ForeignKey("installations.id"), primary_key=True),
    Column("asset_kuid", String(35), ForeignKey("assets.kuid"), primary_key=True),
)


class Asset(Base):
    __tablename__ = "assets"

    kuid = Column(String(35), primary_key=True, nullable=False)
    username = Column(String(255), nullable=False)
    sha1 = Column(String(40), nullable=False)
    revision = Column(Integer, nullable=False)
    last_modified = Column(DateTime, default=func.now(), nullable=False)

    # Foreign key to the last installation
    installations = relationship("Installation", secondary=installation_assets, back_populates="assets")

    def __repr__(self):
        return f"<Asset(kuid={self.kuid}, revision={self.revision})>"


class Installation(Base):
    __tablename__ = "installations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_revision = Column(Integer, nullable=False)
    started_at = Column(DateTime, default=func.now(), nullable=False)
    finished_at = Column(DateTime, nullable=True)
    install_path = Column(String(255), nullable=True)
    additional_options = Column(JSON, nullable=True)
    cancelled = Column(Boolean, default=False, nullable=False)

    # Relationship to assets
    assets = relationship("Asset", secondary=installation_assets, back_populates="installations")

    def __repr__(self):
        return f"<Installation(id={self.id}, from_revision={self.from_revision}, cancelled={self.cancelled})>"
