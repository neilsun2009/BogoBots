nohup \
streamlit run BogoBots.py \
--server.headless true \
--server.address 0.0.0.0 \
--server.port 8601 \
--client.gatherUsageStats false \
> output.log 2>&1 &