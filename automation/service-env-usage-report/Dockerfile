FROM python:3.9-alpine
COPY requirements.txt query_prom_email.py /home/
WORKDIR /home
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT ["python"]
# CMD ["query_prom_email.py"]

# docker build -t 340077773684.dkr.ecr.ap-south-1.amazonaws.com/stage-usage-report:1 .
# docker push 340077773684.dkr.ecr.ap-south-1.amazonaws.com/stage-usage-report:1
