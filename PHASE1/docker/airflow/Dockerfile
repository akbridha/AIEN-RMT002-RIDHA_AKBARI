# Image khusus orkestrasi simulasi milestone P1M1.
# Base image resmi Apache Airflow sudah membawa CLI, webserver, dan scheduler —
# tidak perlu dependensi tambahan karena mode simulasi TIDAK menghubungi
# database maupun menjalankan operasi ingestion/build/transform nyata.
# Saat PIPELINE_MODE=real diaktifkan (Hari 2-4), tambahkan pip install
# dependensi pipeline (mis. pg8000) di sini.
FROM apache/airflow:2.10.4-python3.12
