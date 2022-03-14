from flask import Flask
from dotenv import load_dotenv
from flask import render_template, request, redirect, flash, url_for
from flask import send_from_directory
from flaskext.mysql import MySQL
from datetime import datetime
import os
import yaml
from azure.storage.blob import ContainerClient, BlobServiceClient

load_dotenv()

app= Flask(__name__)
app.secret_key="DevOps"

mysql= MySQL()
app.config['MYSQL_DATABASE_HOST']=os.getenv('DB_HOST',"localhost")
app.config['MYSQL_DATABASE_USER']=os.getenv('DB_USER',"root")
app.config['MYSQL_DATABASE_PASSWORD']=os.getenv('DB_PASSWORD',"")
app.config['MYSQL_DATABASE_DB']=os.getenv('DB_NAME',"sistema")
print(app.config)
mysql.init_app(app)

CARPETA= os.path.join('uploads')
app.config['CARPETA']=CARPETA


def load_config():
	dir_root = os.path.dirname(os.path.abspath(__file__))

	with open(dir_root + "/config.yaml", "r") as yamlfile:
		return yaml.load(yamlfile, Loader=yaml.FullLoader)
config = load_config()



@app.route('/uploads/<nombreFoto>')
def uploads(nombreFoto):
    return send_from_directory(app.config['CARPETA'], nombreFoto)

@app.route('/')
def index():
    sql="SELECT * FROM `empleados`;"
    conn=mysql.connect()
    cursor=conn.cursor()
    cursor.execute(sql)

    empleados=cursor.fetchall()

    conn.commit()

    return render_template('empleados/index.html', empleados=empleados)

@app.route('/destroy/<int:id>')
def destroy(id):
    conn=mysql.connect()
    cursor=conn.cursor()
    cursor.execute("SELECT foto FROM empleados WHERE id=%s",id)
    fila=cursor.fetchall()
    _azure_storage = config["azure_storage_connectionstring"]
    _azure_container = config["file_container_name"]
    container_client = ContainerClient.from_connection_string(_azure_storage, _azure_container)

    container_client.get_blob_client(fila).DeleteIfExists()
    
    os.remove(os.path.join(app.config['CARPETA'],fila[0][0]))
    cursor.execute("DELETE FROM empleados WHERE id=%s",(id))
    conn.commit()
    return redirect('/')

@app.route('/edit/<int:id>')
def edit(id):
    conn=mysql.connect()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM empleados WHERE id=%s",id)
    empleados=cursor.fetchall()
    conn.commit()
    return render_template('empleados/edit.html', empleados=empleados)

@app.route('/update', methods=['POST'])
def update():
    _nombre=request.form['txtNombre']
    _correo=request.form['txtCorreo']
    _foto=request.files['txtFoto']
    id=request.form['txtID']

    sql="UPDATE empleados SET nombre=%s, correo=%s WHERE id=%s;"
    datos=(_nombre , _correo , id)
    conn=mysql.connect()
    cursor=conn.cursor()

    now= datetime.now()
    tiempo= now.strftime("%Y%H%M%S")

    if _foto.filename!='':
        nuevoNombreFoto=tiempo+_foto.filename
        _foto.save("uploads/"+nuevoNombreFoto)
        cursor.execute("SELECT foto FROM empleados WHERE id=%s",id)
        fila=cursor.fetchall()
        os.remove(os.path.join(app.config['CARPETA'],fila[0][0]))
        cursor.execute("UPDATE empleados SET foto=%s WHERE id=%s",(nuevoNombreFoto,id))
        conn.commit()

    if _nombre=='' or _correo=='' or _foto.filename=='':
        flash("Recuerda llenar los datos de los campos")
        cursor.execute("SELECT * FROM empleados WHERE id=%s",id)
        empleados=cursor.fetchall()
        return render_template('empleados/edit.html', empleados=empleados)
    else:
        cursor.execute(sql, datos)
        conn.commit()
    return redirect('/')

@app.route('/create')
def create():
    return render_template ('empleados/create.html')


@app.route('/store', methods=['POST'])
def storage():
    _azure_storage = config["azure_storage_connectionstring"]
    _azure_container = config["file_container_name"]
    _nombre=request.form['txtNombre']
    _correo=request.form['txtCorreo']
    _foto=request.files['txtFoto']
    container_client = ContainerClient.from_connection_string(_azure_storage, _azure_container)

    if _nombre=='' or _correo=='' or _foto.filename=='':
        flash("Recuerda llenar los datos de los campos")
        return redirect(url_for('create'))
    else:
        now= datetime.now()
        tiempo= now.strftime("%Y%H%M%S")

        if _foto.filename!='':
            nuevoNombreFoto=tiempo+_foto.filename
            blob_client = container_client.get_blob_client(_foto.filename)
            blob_client.upload_blob(_foto.stream.read(), overwrite=True)
            print(f'{_foto.name} uploaded to blob storage')
            

        sql="INSERT INTO `empleados` (`id`, `nombre`, `correo`, `foto`) VALUES (NULL, %s, %s, %s);"
        datos=(_nombre , _correo , nuevoNombreFoto)
        
        conn=mysql.connect()
        cursor=conn.cursor()
        cursor.execute(sql, datos)
        conn.commit()
    return redirect(url_for('index'))


if __name__=='__main__':
    app.run(debug=True)


