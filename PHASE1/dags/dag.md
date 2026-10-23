?Bagaimana cara DAG mengetahui suatu script berhasil atau fail.
Q= Bagaimana task dinyatakan berhasil atau gagal?
Berhasil (success): fungsi yang dipanggil PythonOperator selesai tanpa melempar exception. Hasil return, termasuk dictionary, boleh dikirim ke log/XCom, tetapi Airflow tidak otomatis menilai isinya. Contohnya, return {"passed": False} tetap dianggap berhasil jika tidak ada exception.
Gagal (failed): fungsi melempar exception yang tidak ditangani—misalnya FileNotFoundError, RuntimeError, atau AirflowException. Di mode nyata, DAG meneruskan error dari fungsi pipeline melalui _execute_real() di dag.py.
Quality gate: pada mode nyata, DAG memanggil fungsi quality_gate.run(). Jika pemeriksaan gagal, fungsi itu melempar RuntimeError; Airflow kemudian menandai task quality_gate sebagai gagal. Kegagalan tidak sekadar disimpulkan dari isi hasil pemeriksaan.
Mode simulasi: jika dipaksa gagal dengan simulate_gate_failure, fungsi quality gate melempar AirflowException secara sengaja di bagian quality_gate.


yang ada sekarnag bisa jadi terskip gold karena quality_gate gagal


? Apa yang terjadi jika DAG ini saya jalankan ulang padahal data RAW nya sama dan sudah masuk pemprosesan. apa yang akan terjadi?

data RAW yang identik tidak menambah duplikat di Bronze atau Silver, tetapi pipeline tetap menjalankan ulang pemrosesan dan membangun ulang Gold. Riwayat run tetap dibedakan lewat pipeline_run_id.