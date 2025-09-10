# Gunakan Python base image
FROM python:3.11-slim

# Set direktori kerja dalam container
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependency
RUN pip install --no-cache-dir -r requirements.txt

# Install Jupyter (kalau belum ada di requirements.txt)
RUN pip install jupyter

# Copy semua file project (opsional kalau ada kode selain notebook)
COPY . .

# Expose port untuk Jupyter
EXPOSE 8888

# Jalankan Jupyter Notebook
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--allow-root", "--no-browser"]
