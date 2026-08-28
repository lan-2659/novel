from sqlalchemy.orm import Session

from ..models.entities import Volume
from ..pipeline.stages import VOLUME_STAGE_OUTLINE, VOLUME_STATUS_DRAFT


class VolumeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, project_id: int, number: int, title: str = "") -> Volume:
        volume = Volume(
            project_id=project_id,
            number=number,
            title=title or f"第{number}卷",
            status=VOLUME_STATUS_DRAFT,
            stage=VOLUME_STAGE_OUTLINE,
        )
        self.db.add(volume)
        self.db.commit()
        self.db.refresh(volume)
        return volume

    def list(self, project_id: int) -> list[Volume]:
        return (
            self.db.query(Volume)
            .filter_by(project_id=project_id)
            .order_by(Volume.number)
            .all()
        )

    def get(self, volume_id: int) -> Volume | None:
        return self.db.get(Volume, volume_id)

    def get_by_number(self, project_id: int, number: int) -> Volume | None:
        return (
            self.db.query(Volume)
            .filter_by(project_id=project_id, number=number)
            .first()
        )

    def next_number(self, project_id: int) -> int:
        last = (
            self.db.query(Volume)
            .filter_by(project_id=project_id)
            .order_by(Volume.number.desc())
            .first()
        )
        return (last.number + 1) if last else 1

    def save(self, volume: Volume, **fields: object) -> Volume:
        for key, value in fields.items():
            if value is not None:
                setattr(volume, key, value)
        self.db.commit()
        self.db.refresh(volume)
        return volume
