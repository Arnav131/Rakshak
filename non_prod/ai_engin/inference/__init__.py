"""
Rakshak AI Engine — Inference Module
=======================================
Production inference pipeline for the Django backend.

Import this module to run predictions on live sensor data:

    from ai_engin.inference.pipeline import RakshakInferencePipeline
    pipeline = RakshakInferencePipeline(model_dir="ai_engin/trained_models/")
    result = pipeline.predict(ambient_temp=42.5, humidity=22.0, ...)
"""
