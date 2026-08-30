from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/clfis_db"
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days; there is no refresh-token flow
    
    # CORS. Set ALLOWED_ORIGINS in the environment to serve the app from a LAN
    # address; localStorage and CORS are both per-origin, so a host that is not
    # listed here cannot sign in.
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    # Campus Email Domain
    CAMPUS_EMAIL_DOMAIN: str = os.getenv("CAMPUS_EMAIL_DOMAIN", "college.edu")
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "backend/uploads"
    
    # ML Models -- two towers, chosen for different jobs.
    #
    # Text: SigLIP. Its caption-aligned space is a good semantic match for two
    # people describing the same object in their own words.
    SIGLIP_MODEL: str = "google/siglip-base-patch16-224"
    #
    # Images: DINOv2, NOT SigLIP. SigLIP is trained to align images with captions,
    # so it is deliberately invariant to instance detail -- measured on real
    # uploads it scored two different Motorola handsets (0.86) HIGHER than the
    # same iPhone re-photographed (0.68), inverting the ranking. DINOv2 is
    # self-supervised with no text supervision, so it keeps the fine-grained
    # appearance detail that re-identification depends on. Both are 768-d, so the
    # Vector(768) columns are unchanged.
    DINOV2_MODEL: str = "facebook/dinov2-base"
    #
    # Set EMBEDDINGS_ENABLED=false to skip loading both models. Matching still
    # runs, but the visual and text terms stay 0 and only category, decay and the
    # OCR bonus contribute -- which on its own rarely clears the POTENTIAL
    # threshold. Useful for a lightweight deploy or a fast test run.
    EMBEDDINGS_ENABLED: bool = True
    # "auto" uses the GPU when torch reports one and falls back to CPU otherwise.
    # Force with "cuda" or "cpu". An explicit "cuda" never degrades to CPU: if the
    # device is unusable the load fails loudly in the log and matching runs without
    # embeddings, rather than quietly running 20x slower than the deploy intended.
    EMBEDDING_DEVICE: str = "auto"

    # Load the embedding models in a background thread at startup instead of on
    # the first report. Lazy loading keeps startup instant, but it hands the cost
    # to whoever files the first report -- measured at ~8s (SigLIP 6.7s, DINOv2
    # 1.2s), which reads as "matching is slow" when it is really "matching is
    # slow once". Warming in a daemon thread keeps startup non-blocking and has
    # the weights resident before anyone submits. Set false on a memory-tight
    # box, where paying the 8s once is better than holding ~750MB permanently.
    WARM_EMBEDDINGS_ON_STARTUP: bool = True

    # Crop to the salient object before embedding, so the same item photographed
    # in different surroundings still matches itself. Set false to embed the
    # whole frame instead.
    OBJECT_CROP: bool = True

    # Zero-shot brand reading. A confident disagreement ("this is a Motorola,
    # that is an Apple") is strong evidence two items are NOT the same object,
    # even when they look alike. Blank the vocabulary to disable the check.
    BRAND_VOCABULARY: str = (
        "Apple,Samsung,Motorola,OnePlus,Xiaomi,Realme,Vivo,Oppo,Nokia,Google,"
        "Dell,HP,Lenovo,Asus,Acer,Sony,JBL,Boat,Nike,Adidas,Puma,Titan,Fastrack"
    )
    # Below this the brand is recorded as unknown. Unknown never counts as a
    # mismatch -- only a confident disagreement penalises a pair.
    BRAND_MIN_CONFIDENCE: float = 0.08
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()
