Folder PATH listing for volume Windows
Volume serial number is 00000007 A81E:4E21
D:.
│   .env
│   .env.example
│   .gitignore
│   AI_ENGINE_GUIDE.md
│   check_all_py.py
│   Codebase.md
│   improvements.md
│   PROGRESS_REPORT.md
│   PROJECT_REPORT.md
│   README.md
│   requirements.txt
│   rundatabase.md
│   test_progress.md
│   Tree.md
│
├───ai_engin
│   ├───colab_training
│   │   ├───data
│   │   │   ├───__init__.py
│   │   │   ├───data_loader.py
│   │   │   ├───dataset.py
│   │   │   ├───feature_engineer.py
│   │   │   └───preprocessing.py
│   │   ├───evaluation
│   │   │   ├───__init__.py
│   │   │   ├───evaluate_all.py
│   │   │   └───visualization.py
│   │   ├───export
│   │   │   ├───__init__.py
│   │   │   └───export_models.py
│   │   ├───models
│   │   │   ├───__init__.py
│   │   │   ├───failure_predictor.py
│   │   │   ├───fault_classifier.py
│   │   │   ├───isolation_forest.py
│   │   │   ├───meta_classifier.py
│   │   │   └───vae_anomaly.py
│   │   ├───training
│   │   │   ├───__init__.py
│   │   │   ├───losses.py
│   │   │   ├───metrics.py
│   │   │   ├───train_classifier.py
│   │   │   ├───train_ensemble.py
│   │   │   ├───train_failure.py
│   │   │   └───train_vae.py
│   │   ├───config.py
│   │   └───train_all_models.ipynb
│   ├───inference
│   │   ├───__init__.py
│   │   ├───anomaly_detector.py
│   │   ├───failure_predictor.py
│   │   ├───fault_classifier.py
│   │   ├───model_registry.py
│   │   ├───pipeline.py
│   │   ├───utils.py
│   │   └───__pycache__
│   ├───trained_models
│   │   └───.gitkeep
│   ├───agents_README.md
│   └───requirements_colab.txt
│
├───backend
│   ├───agents
│   │   ├───__init__.py
│   │   ├───anomaly
│   │   │   └───anomaly_detection_agent.py
│   │   ├───dispatch
│   │   │   └───maintenance_dispatch_agent.py
│   │   ├───explainability
│   │   │   └───explainability_agent.py
│   │   ├───ingestion
│   │   │   └───sensor_ingestion_agent.py
│   │   ├───network_health
│   │   │   └───network_health_agent.py
│   │   ├───prediction
│   │   │   └───failure_prediction_agent.py
│   │   ├───root_cause
│   │   │   └───root_cause_agent.py
│   │   ├───shared
│   │   │   ├───__init__.py
│   │   │   ├───base_agent.py
│   │   │   └───events.py
│   │   └───speed_restriction
│   │       └───speed_restriction_agent.py
│   ├───ai_integration
│   │   ├───__init__.py
│   │   ├───alert_service.py
│   │   ├───api_urls.py
│   │   ├───api_views.py
│   │   ├───apps.py
│   │   ├───incident_orchestrator.py
│   │   ├───journey_service.py
│   │   ├───journey_urls.py
│   │   ├───journey_views.py
│   │   ├───local_provider.py
│   │   ├───mock_sensor_generator.py
│   │   ├───prediction_service.py
│   │   ├───providers.py
│   │   ├───registry.py
│   │   ├───sensor_source.py
│   │   ├───serializers.py
│   │   ├───tests
│   │   │   ├───__init__.py
│   │   │   ├───test_prediction_service.py
│   │   │   └───test_providers.py
│   │   └───ticket_service.py
│   ├───ai_models
│   │   ├───model_config.json
│   │   └───simple_pipeline.py
│   ├───alerts
│   │   ├───__init__.py
│   │   ├───urls.py
│   │   └───views.py
│   ├───check_templates.py
│   ├───core
│   │   ├───__init__.py
│   │   ├───context_processors.py
│   │   └───utils.py
│   ├───manage.py
│   ├───map_view
│   │   ├───__init__.py
│   │   ├───api_urls.py
│   │   ├───api_views.py
│   │   ├───route_geometry
│   │   │   └───india_railways.geojson
│   │   ├───services.py
│   │   ├───urls.py
│   │   └───views.py
│   ├───railway
│   │   ├───__init__.py
│   │   ├───admin.py
│   │   ├───apps.py
│   │   ├───build_complete_india_osm_network.py
│   │   ├───build_railway_data.py
│   │   ├───download_full_india_osm_railways.py
│   │   ├───extract_osm_test.py
│   │   ├───fetch_real_india_railways.py
│   │   ├───generate_dense_india_railways.py
│   │   ├───generate_osm_railway_dataset.py
│   │   ├───management
│   │   │   └───commands
│   │   │       ├───__init__.py
│   │   │       ├───seed_demo_data.py
│   │   │       ├───seed_master_data.py
│   │   │       ├───seed_routes.py
│   │   │       └───seed_sensors.py
│   │   ├───migrations
│   │   │   ├───0001_initial.py
│   │   │   ├───0002_tracksection_uniq_track_route_direction.py
│   │   │   ├───0003_tracksection_geometry.py
│   │   │   └───__init__.py
│   │   ├───middleware.py
│   │   ├───models.py
│   │   ├───signals.py
│   │   ├───test_grid_query.py
│   │   ├───tests.py
│   │   ├───verify_final_map.py
│   │   └───views.py
│   ├───rakshak_project
│   │   ├───__init__.py
│   │   ├───asgi.py
│   │   ├───settings.py
│   │   ├───urls.py
│   │   └───wsgi.py
│   ├───sensors
│   │   ├───__init__.py
│   │   ├───api_urls.py
│   │   ├───api_views.py
│   │   ├───urls.py
│   │   └───views.py
│   ├───simulation
│   │   ├───__init__.py
│   │   ├───api_urls.py
│   │   ├───generator.py
│   │   ├───tests.py
│   │   ├───urls.py
│   │   └───views.py
│   ├───test_queries.py
│   ├───validate_api.py
│   └───verify_endpoints.py
│
├───demo_assets
│   └───demo_scenario.md
│
├───docs
│   ├───architecture
│   │   └───system_overview.md
│   └───reports
│       └───PHASE_REPORT.md
│
├───frontend
│   ├───static
│   │   ├───css
│   │   │   ├───dashboard.css
│   │   │   └───simulation.css
│   │   ├───images
│   │   │   └───.gitkeep
│   │   └───js
│   │       ├───dashboard.js
│   │       ├───map.js
│   │       ├───simulation.js
│   │       └───train_simulation.js
│   └───templates
│       ├───base.html
│       ├───dashboard.html
│       ├───map.html
│       ├───simulation.html
│       └───tickets.html
│
├───notebooks
│   ├───colab_training_tutorial.md
│   ├───requirements-colab.txt
│   ├───section_0.py
│   ├───section_1.py
│   ├───section_2.py
│   ├───section_3.py
│   ├───section_4.py
│   ├───section_5.py
│   ├───section_6.py
│   ├───section_7.py
│   ├───SHARED_CONTRACT.md
│   ├───train_colab.ipynb
│   └───train_colab.py
│
├───presentation
│   └───.gitkeep
│
└───venv
