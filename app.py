from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls'}

# Verificar extensão do arquivo
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Rota principal
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo enviado')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('Nenhum arquivo selecionado')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            
            file.save(filepath)
            
            try:
                db_filename = process_excel_file(filepath)
                session['current_db'] = db_filename
                session['current_table'] = os.path.splitext(os.path.basename(filepath))[0].replace(' ', '_').lower()
                flash('Arquivo processado com sucesso! Banco de dados criado.')
                return redirect(url_for('filter_data'))
            except Exception as e:
                flash(f'Erro ao processar arquivo: {str(e)}')
    
    return render_template('upload.html')

def process_excel_file(filepath):
    # Ler arquivo Excel
    df = pd.read_excel(filepath)
    
    # Gerar nomes para arquivos
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    csv_filename = f"{base_name}.csv"
    db_filename = f"{base_name}.db"
    
    # Converter para CSV
    df.to_csv(os.path.join(app.config['UPLOAD_FOLDER'], csv_filename), index=False)
    
    # Criar banco de dados SQLite
    conn = sqlite3.connect(os.path.join(app.config['UPLOAD_FOLDER'], db_filename))
    
    # Usar o nome do arquivo (sem extensão) como nome da tabela
    table_name = base_name.replace(' ', '_').lower()
    
    # Salvar DataFrame no banco de dados
    df.to_sql(table_name, conn, if_exists='replace', index=False)
    
    conn.close()
    return db_filename

@app.route('/filter', methods=['GET', 'POST'])
def filter_data():
    if 'current_db' not in session:
        flash('Nenhum banco de dados carregado. Por favor, envie um arquivo Excel primeiro.')
        return redirect(url_for('upload_file'))
    
    db_path = os.path.join(app.config['UPLOAD_FOLDER'], session['current_db'])
    table_name = session['current_table']
    
    # Conectar ao banco de dados
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Obter informações da tabela
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Processar filtros
    if request.method == 'POST':
        selected_column = request.form.get('column')
        filter_value = request.form.get('filter_value')
        
        if selected_column and filter_value:
            # Construir query com filtro (usando LIKE para busca parcial)
            query = f"SELECT * FROM {table_name} WHERE {selected_column} LIKE ?"
            cursor.execute(query, (f'%{filter_value}%',))
        else:
            # Sem filtro, trazer todos os dados
            cursor.execute(f"SELECT * FROM {table_name}")
    else:
        # Primeiro acesso, trazer todos os dados
        cursor.execute(f"SELECT * FROM {table_name}")
    
    # Obter resultados
    data = cursor.fetchall()
    
    # Obter nomes das colunas para exibição
    column_names = [description[0] for description in cursor.description]
    
    conn.close()
    
    return render_template('filter.html', 
                         columns=columns, 
                         data=data, 
                         column_names=column_names,
                         table_name=table_name)

@app.route('/reset', methods=['POST'])
def reset_filters():
    return redirect(url_for('filter_data'))

if __name__ == '__main__':
    app.run(debug=True)