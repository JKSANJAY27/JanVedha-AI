"""
MongoDB Document: MediaRtiResponse

Stores drafted responses to media queries and RTI applications,
grounded in real ticket data from the ward.
Collection: media_rti_responses
"""
import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Literal
from beanie import Document, Indexed
from pydantic import BaseModel, Field


class QueryInput(BaseModel):
    query_text: str
    query_image_path: Optional[str] = None
    query_source: Optional[str] = None       # journalist / outlet / applicant name
    date_received: Optional[date] = None
    rti_application_number: Optional[str] = None
    tone_preference: Optional[Literal["data_forward", "empathetic", "firm"]] = None


class DataPoint(BaseModel):
    description: str
    data: Dict[str, Any] = Field(default_factory=dict)


class DataAnalysis(BaseModel):
    query_intent: Optional[str] = None
    is_answerable: bool = True
    data_points: List[DataPoint] = Field(default_factory=list)
    outside_scope: List[str] = Field(default_factory=list)
    sensitivity_flag: bool = False
    sensitivity_note: Optional[str] = None


class MediaOutputContent(BaseModel):
    quotable_statement: Optional[str] = None
    supporting_data_points: List[str] = Field(default_factory=list)
    full_response_letter: Optional[str] = None
    data_gaps_note: Optional[str] = None


class RtiDocumentHeader(BaseModel):
    office_name: str = ""
    application_number: str = ""
    date_of_receipt: str = ""
    date_of_response: str = ""
    response_deadline: str = ""


class RtiInfoItem(BaseModel):
    query_item: str
    response: str
    data_basis: Optional[str] = None


class RtiNotAvailableItem(BaseModel):
    query_item: str
    reason: str


class RtiSignatureBlock(BaseModel):
    name: str = ""
    designation: str = ""
    ward: str = ""
    date: str = ""


class RtiDocument(BaseModel):
    header: RtiDocumentHeader = Field(default_factory=RtiDocumentHeader)
    applicant_reference: str = ""
    acknowledgment_paragraph: str = ""
    information_provided: List[RtiInfoItem] = Field(default_factory=list)
    information_not_held: List[RtiNotAvailableItem] = Field(default_factory=list)
    closing_paragraph: str = ""
    signature_block: RtiSignatureBlock = Field(default_factory=RtiSignatureBlock)


class RtiOutputContent(BaseModel):
    rti_response_document: Optional[RtiDocument] = None
    internal_note: Optional[str] = None


class ResponseOutput(BaseModel):
    media_response: Optional[MediaOutputContent] = None
    rti_response: Optional[RtiOutputContent] = None


class MediaRtiResponseMongo(Document):
    response_id: Indexed(str, unique=True) = Field(  # type: ignore[valid-type]
        default_factory=lambda: uuid.uuid4().hex[:10]
    )
    ward_id: Indexed(str)  # type: ignore[valid-type]
    councillor_id: str
    councillor_name: str
    ward_name: str

    type: Literal["media", "rti"]
    input: QueryInput
    data_analysis: DataAnalysis = Field(default_factory=DataAnalysis)
    output: ResponseOutput = Field(default_factory=ResponseOutput)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "media_rti_responses"
        indexes = [
            "ward_id",
            "councillor_id",
            "type",
            "created_at",
        ]

    class Config:
        populate_by_name = True
