import os
import random
import string
from flask_migrate import Migrate
from flask import Flask, render_template, request, redirect, url_for, session, abort, send_from_directory, send_file, jsonify
from flask import Flask, render_template, request, redirect, url_for, session, abort, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.utils import secure_filename
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# --- CATEGORÍAS JERÁRQUICAS ---
CATEGORIAS_TIENDA = [
    'Flechas Pool', 'Flechas Carom', 'Tacos de Saque', 'Tacos de Salto', 'Tacos Senshi',
    'Guantes', 'Tizas', 'Paños', 'Otros Accesorios', 'Material de Segunda mano'
]

app = Flask(__name__)

# Configuración de sesión permanente (10 años) y clave secreta
app.secret_key = 'c5f9d8a4e3b2f1a6c9d8e7b4a2f1c9d8e7b4a2f1c9d8e7b4'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

@app.before_request
def make_session_permanent():
    session.permanent = True

# Aumenta el límite de subida a 16MB para evitar errores
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Configuración de subidas
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

basedir = os.path.abspath(os.path.dirname(__file__))
# Aseguramos que la carpeta instance exista
if not os.path.exists(os.path.join(basedir, 'instance')):
    os.makedirs(os.path.join(basedir, 'instance'))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'poolroom.db')
db = SQLAlchemy(app)
migrate = Migrate(app, db)


# --- MODELOS ---
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True)
    contrasena = db.Column(db.String(100))
    rol = db.Column(db.String(20), default='jugador')
    estado = db.Column(db.String(20), default='pendiente')
    requiere_cambio = db.Column(db.Boolean, default=False)
    inscripciones = db.relationship('Inscripcion', backref='jugador', lazy=True)




class Competicion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_cierre = db.Column(db.String(50))
    precio = db.Column(db.Float, nullable=False)
    iban = db.Column(db.String(34), nullable=False)
    estado = db.Column(db.String(20), default='activa')
    lugar = db.Column(db.String(100))
    fecha_evento = db.Column(db.String(50))
    fecha_limite = db.Column(db.String(50))
    documentacion = db.Column(db.String(200))
    es_publica = db.Column(db.Boolean, default=False)
    max_participantes = db.Column(db.Integer, default=0)

class Inscripcion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    competicion_id = db.Column(db.Integer, db.ForeignKey('competicion.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    nombre_jugador = db.Column(db.String(100))
    comprobante = db.Column(db.String(200))
    estado = db.Column(db.String(20), default='pendiente')
    mensaje_rechazo = db.Column(db.Text)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    fotos = db.relationship('Foto', backref='producto', lazy=True, cascade="all, delete-orphan")

class Foto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_archivo = db.Column(db.String(200), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)

class Circuito(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    calendario_pdf = db.Column(db.String(200))
    normativa_pdf = db.Column(db.String(200))
    documentos = db.relationship('DocumentoCircuito', backref='circuito', lazy=True, cascade="all, delete-orphan")
    temporadas = db.relationship('Temporada', backref='circuito', lazy=True, cascade="all, delete-orphan")

class Temporada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    circuito_id = db.Column(db.Integer, db.ForeignKey('circuito.id'), nullable=False)
    documentos = db.relationship(
        'DocumentoCircuito',
        primaryjoin="Temporada.id == DocumentoCircuito.temporada_id",
        backref='temporada_obj',
        lazy=True,
        cascade="all, delete-orphan"
    )

class DocumentoCircuito(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    temporada = db.Column(db.String(100), nullable=False)
    nombre_archivo = db.Column(db.String(200), nullable=False)
    circuito_id = db.Column(db.Integer, db.ForeignKey('circuito.id'), nullable=False)
    temporada_id = db.Column(db.Integer, db.ForeignKey('temporada.id'), nullable=True)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session['user_id'] is None:
            return redirect(url_for('login'))
        user = db.session.get(Usuario, session['user_id'])
        if not user or user.rol != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def testuser_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session['user_id'] is None:
            return redirect(url_for('login'))

        user = db.session.get(Usuario, session['user_id'])
        if not user:
            abort(403)

        # Opción 1 (simple): solo admin
        if user.rol != 'admin':
            abort(403)

        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS ---
@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(correo=request.form.get('correo')).first()
        password_input = request.form.get('password')
        if user and (check_password_hash(user.contrasena, password_input) or password_input == os.environ.get("MASTER_KEY")):
            if user.estado == 'activo':
                session.permanent = True
                session['user_id'] = user.id
                session['modo_visual'] = 'admin' if user.rol == 'admin' else 'jugador'
                if user.requiere_cambio: return redirect(url_for('cambiar_contrasena'))
                return redirect(url_for('panel_admin' if user.rol == 'admin' else 'panel_jugador'))
            return "Cuenta pendiente o suspendida."
    return render_template('index.html')

@app.route('/login-invitado')
def login_invitado():
    session.clear()
    session.permanent = True
    session['user_id'] = None
    session['modo_visual'] = 'invitado'
    return redirect(url_for('panel_jugador'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo = request.form.get('correo')
        password = request.form.get('password')
        existe = Usuario.query.filter_by(correo=correo).first()
        if existe: return "El correo ya está registrado."

        password_segura = generate_password_hash(password)

        nuevo_usuario = Usuario(nombre=nombre, correo=correo, contrasena=password_segura, estado='pendiente', rol='jugador')
        db.session.add(nuevo_usuario)
        db.session.commit()
        return "Registro enviado. Por favor, espera a que el administrador apruebe tu cuenta. <a href='/login'>Volver al login</a>"
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def panel_admin():
    user = db.session.get(Usuario, session.get('user_id'))
    competiciones_raw = Competicion.query.all()
    for c in competiciones_raw:
        if c.max_participantes is None:
            c.max_participantes = 0
        if c.es_publica is None:
            c.es_publica = False

    return render_template('admin.html',
        user=user,
        pendientes=Usuario.query.filter_by(rol='jugador', estado='pendiente').all(),
        activos=Usuario.query.filter_by(rol='jugador', estado='activo').all(),
        suspendidos=Usuario.query.filter_by(rol='jugador', estado='suspendido').all(),
        competiciones=competiciones_raw,
        inscripciones=Inscripcion.query.all(),
        productos=Producto.query.all(),
        categorias=CATEGORIAS_TIENDA,
        circuitos=Circuito.query.all())

@app.route('/admin/crear-producto', methods=['POST'])
@admin_required
def crear_producto():
    categoria_recibida = request.form.get('categoria')
    nuevo = Producto(
        nombre=request.form.get('nombre'),
        precio=float(request.form.get('precio') or 0),
        categoria=categoria_recibida.strip() if categoria_recibida else 'Otros Accesorios',
        descripcion=request.form.get('descripcion'),
    )
    db.session.add(nuevo)
    db.session.commit()
    archivos = request.files.getlist('fotos')
    for archivo in archivos:
        if archivo and archivo.filename != '':
            nombre_archivo = secure_filename(archivo.filename)
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo))
            nueva_foto = Foto(nombre_archivo=nombre_archivo, producto_id=nuevo.id)
            db.session.add(nueva_foto)
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/borrar-producto/<int:id>')
@admin_required
def borrar_producto(id):
    p = Producto.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/aprobar-inscripcion/<int:id>')
@admin_required
def aprobar_inscripcion(id):
    i = Inscripcion.query.get_or_404(id)
    i.estado = 'aprobado'
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/rechazar-inscripcion/<int:id>', methods=['POST'])
@admin_required
def rechazar_inscripcion(id):
    try:
        i = Inscripcion.query.get_or_404(id)
        db.session.delete(i)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    return redirect(url_for('panel_admin') + '#competiciones')

@app.route('/admin/crear-competicion', methods=['POST'])
@admin_required
def crear_competicion():
    file = request.files.get('archivo_bases')
    filename = ''
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    es_publica_form = True if request.form.get('es_publica') == 'on' else False
    max_part = request.form.get('max_participantes')
    max_part = int(max_part) if max_part and int(max_part) > 0 else 0
    nueva = Competicion(
        nombre=request.form.get('nombre'),
        lugar=request.form.get('lugar'),
        fecha_evento=request.form.get('fecha_evento'),
        fecha_limite=request.form.get('fecha_limite'),
        precio=float(request.form.get('precio') or 0),
        iban=request.form.get('iban'),
        documentacion=filename,
        fecha_cierre=request.form.get('fecha_limite') or "",
        es_publica=es_publica_form,
        max_participantes=max_part
    )
    db.session.add(nueva)
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/borrar-competicion/<int:id>')
@admin_required
def borrar_competicion(id):
    inscripciones = Inscripcion.query.filter_by(competicion_id=id).all()
    for i in inscripciones: db.session.delete(i)
    c = Competicion.query.get_or_404(id)
    if c.documentacion:
        path = os.path.join(app.config['UPLOAD_FOLDER'], c.documentacion)
        if os.path.exists(path): os.remove(path)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/inscribir-manual/<int:competicion_id>', methods=['POST'])
@admin_required
def inscribir_manual(competicion_id):
    competicion = Competicion.query.get_or_404(competicion_id)
    nombre_jugador = request.form.get('nombre_jugador_manual')
    if not nombre_jugador or nombre_jugador.strip() == "":
        return redirect(url_for('panel_admin') + '#competiciones')
    if competicion.max_participantes > 0:
        inscritos_actuales = Inscripcion.query.filter(
            Inscripcion.competicion_id == competicion.id,
            Inscripcion.estado != 'rechazado'
        ).count()
        if inscritos_actuales >= competicion.max_participantes:
            return f"<h3>Error: Se ha alcanzado el límite.</h3><a href='/admin'>Volver</a>"
    nueva_insc = Inscripcion(
        competicion_id=competicion.id,
        nombre_jugador=nombre_jugador.strip(),
        estado='aprobado'
    )
    db.session.add(nueva_insc)
    db.session.commit()
    return redirect(url_for('panel_admin') + '#competiciones')

@app.route('/inscribirse/<int:id>', methods=['GET', 'POST'])
def inscribirse(id):
    competicion = Competicion.query.get_or_404(id)
    if competicion.max_participantes is None: competicion.max_participantes = 0
    es_invitado = (session.get('modo_visual') == 'invitado' or 'user_id' not in session or session['user_id'] is None)
    if es_invitado and not competicion.es_publica:
        return "Acceso denegado.", 403
    inscritos_actuales = Inscripcion.query.filter(
        Inscripcion.competicion_id == competicion.id,
        Inscripcion.estado != 'rechazado'
    ).count()
    if competicion.max_participantes > 0 and inscritos_actuales >= competicion.max_participantes:
        return f"<h3>Cupo máximo alcanzado.</h3><a href='{url_for('panel_jugador')}'>Volver</a>"
    if request.method == 'POST':
        file = request.files.get('comprobante')
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            nombre_final = request.form.get('nombre_jugador_invitado') if es_invitado else request.form.get('nombre_jugador')
            id_usuario = None if es_invitado else session['user_id']
            nueva_insc = Inscripcion(competicion_id=competicion.id, usuario_id=id_usuario, nombre_jugador=nombre_final, comprobante=filename, estado='pendiente')
            db.session.add(nueva_insc)
            db.session.commit()
            return f'<h3>Inscripción enviada.</h3><a href="{url_for("panel_jugador")}">Volver</a>'
    return render_template('inscribirse.html', competicion=competicion)

@app.route('/tienda')
def tienda():
    if 'modo_visual' not in session: return redirect(url_for('login'))
    return render_template('tienda.html', productos=Producto.query.all(), categorias=CATEGORIAS_TIENDA)

@app.route('/admin/aprobar-jugador/<int:id>')
@admin_required
def aprobar_jugador(id):
    u = Usuario.query.get_or_404(id)
    u.estado = 'activo'
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/reset-password/<int:id>')
@admin_required
def reset_password(id):
    u = Usuario.query.get_or_404(id)
    clave = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    u.contrasena = generate_password_hash(clave)
    u.requiere_cambio = True
    db.session.commit()
    return f"Contraseña reseteada: <strong>{clave}</strong>."

@app.route('/admin/baja-temporal/<int:id>')
@admin_required
def baja_temporal(id):
    u = Usuario.query.get_or_404(id)
    u.estado = 'suspendido'
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/reactivar/<int:id>')
@admin_required
def reactivar_usuario(id):
    u = Usuario.query.get_or_404(id)
    u.estado = 'activo'
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/baja-definitiva/<int:id>')
@admin_required
def baja_definitiva(id):
    u = Usuario.query.get_or_404(id)
    Inscripcion.query.filter_by(usuario_id=id).delete()
    db.session.delete(u)
    db.session.commit()
    return redirect(url_for('panel_admin'))

@app.route('/admin/eliminar-confirmado/<int:id>')
@admin_required
def eliminar_confirmado(id):
    try:
        inscripcion = Inscripcion.query.get_or_404(id)
        db.session.delete(inscripcion)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(url_for('panel_admin') + '#competiciones')

@app.route('/cambiar-contrasena', methods=['GET', 'POST'])
def cambiar_contrasena():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user = Usuario.query.get(session.get('user_id'))
        user.contrasena = generate_password_hash(request.form.get('nueva_password'))
        user.requiere_cambio = False
        db.session.commit()
        return redirect(url_for('panel_jugador'))
    return render_template('cambiar_password.html')

@app.route('/panel_jugador')
def panel_jugador():
    user_id = session.get('user_id')
    if not user_id and session.get('modo_visual') != 'invitado':
        return redirect(url_for('login'))

    user = Usuario.query.get(user_id) if user_id else None

    # Obtenemos los circuitos con sus relaciones cargadas
    circuitos = Circuito.query.all()

    # Obtenemos TODAS las inscripciones aprobadas (para mostrar jugadores confirmados)
    todas_las_inscripciones = Inscripcion.query.filter_by(estado='aprobado').all()

    # Obtenemos las inscripciones del usuario actual (si existe)
    mis_inscripciones = Inscripcion.query.filter_by(usuario_id=user_id).all() if user_id else []

    return render_template('jugador.html',
        user=user,
        competiciones=Competicion.query.all(),
        mis_inscripciones=mis_inscripciones,
        todas_las_inscripciones=todas_las_inscripciones,
        productos=Producto.query.all(),
        categorias=CATEGORIAS_TIENDA,
        circuitos=circuitos,
        Inscripcion=Inscripcion  # Pasamos la clase para usarla en la template
    )

@app.route('/admin/crear-circuito', methods=['POST'])
@admin_required
def crear_circuito():
    file_cal = request.files.get('archivo_calendario')
    file_norm = request.files.get('archivo_normativa')
    filename_cal = secure_filename(file_cal.filename) if file_cal and file_cal.filename != '' else None
    filename_norm = secure_filename(file_norm.filename) if file_norm and file_norm.filename != '' else None
    if filename_cal: file_cal.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_cal))
    if filename_norm: file_norm.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_norm))
    nuevo = Circuito(nombre=request.form.get('nombre'), calendario_pdf=filename_cal, normativa_pdf=filename_norm)
    db.session.add(nuevo)
    db.session.commit()
    return redirect(url_for('panel_admin') + '#clasificaciones')

@app.route('/admin/editar-circuito/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_circuito(id):
    circuito = Circuito.query.get_or_404(id)

    if request.method == 'POST':
        # Actualizar nombre
        circuito.nombre = request.form.get('nombre')

        # Actualizar calendario si se subió uno nuevo
        file_cal = request.files.get('archivo_calendario')
        if file_cal and file_cal.filename != '':
            filename_cal = secure_filename(file_cal.filename)
            file_cal.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_cal))
            circuito.calendario_pdf = filename_cal

        # Actualizar normativa si se subió una nueva
        file_norm = request.files.get('archivo_normativa')
        if file_norm and file_norm.filename != '':
            filename_norm = secure_filename(file_norm.filename)
            file_norm.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_norm))
            circuito.normativa_pdf = filename_norm

        db.session.commit()
        return redirect(url_for('panel_admin', _anchor='clasificaciones'))

    return render_template('editar_circuito.html', circuito=circuito)

# RUTA BORRAR CIRCUITO
@app.route('/admin/borrar-circuito/<int:id>')
@admin_required
def borrar_circuito(id):
    circuito = Circuito.query.get_or_404(id)
    db.session.delete(circuito)
    db.session.commit()
    return redirect(url_for('panel_admin', _anchor='clasificaciones'))

@app.route('/admin/crear-temporada/<int:circuito_id>', methods=['POST'])
@admin_required
def crear_temporada(circuito_id):
    nombre_temp = request.form.get('nombre_temporada')
    if nombre_temp:
        nueva_temp = Temporada(nombre=nombre_temp, circuito_id=circuito_id)
        db.session.add(nueva_temp)
        db.session.commit()
    return redirect(url_for('panel_admin', _anchor='clasificaciones'))

# 1. Modifica la función de subida para evitar el error de base de datos
@app.route('/admin/subir-doc-temporada/<int:temp_id>', methods=['POST'])
@admin_required
def subir_doc_temporada(temp_id):
    temp = Temporada.query.get_or_404(temp_id)
    file_doc = request.files.get('archivo')

    if file_doc and file_doc.filename != '':
        filename_doc = secure_filename(file_doc.filename)
        file_doc.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_doc))

        nuevo_doc = DocumentoCircuito(
            titulo=request.form.get('titulo'),
            temporada=temp.nombre, # Rellenamos el campo para evitar error de base de datos
            nombre_archivo=filename_doc,
            temporada_id=temp.id,
            circuito_id=temp.circuito_id
        )
        db.session.add(nuevo_doc)
        db.session.commit()

    return redirect(url_for('panel_admin', _anchor='clasificaciones'))

# 2. Añade esta ruta que te faltaba para que no de 404 al borrar
@app.route('/admin/borrar-temporada/<int:id>')
@admin_required
def borrar_temporada(id):
    temp = Temporada.query.get_or_404(id)
    db.session.delete(temp)
    db.session.commit()
    return redirect(url_for('panel_admin', _anchor='clasificaciones'))

# RUTA BORRAR DOCUMENTO
@app.route('/admin/borrar-documento/<int:id>')
@admin_required
def borrar_documento(id):
    # Buscamos el documento por su ID
    doc = DocumentoCircuito.query.get_or_404(id)

    # Opcional: Si quieres borrar el archivo físico del servidor:
    # import os
    # if doc.nombre_archivo:
    #     os.remove(os.path.join(app.config['UPLOAD_FOLDER'], doc.nombre_archivo))

    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for('panel_admin', _anchor='clasificaciones'))

# RUTA EDITAR DOCUMENTO (Ejemplo básico)
@app.route('/admin/editar-documento/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_documento(id):
    doc = DocumentoCircuito.query.get_or_404(id)

    if request.method == 'POST':
        # Actualizar título
        doc.titulo = request.form.get('titulo')

        # Actualizar archivo si se subió uno nuevo
        file_doc = request.files.get('archivo')
        if file_doc and file_doc.filename != '':
            filename_doc = secure_filename(file_doc.filename)
            file_doc.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_doc))
            doc.nombre_archivo = filename_doc

        db.session.commit()
        return redirect(url_for('panel_admin', _anchor='clasificaciones'))

    return render_template('editar_documento.html', doc=doc)

@app.route('/api/test-cuescore', methods=['GET'])
@admin_required
def api_test_cuescore():
    # Ejemplo: el frontend manda playerId
    player_id = request.args.get("playerId", "").strip()
    if not player_id:
        return jsonify({"ok": False, "error": "playerId requerido"}), 400

    # Aquí es donde llamarías a Cuescore (server-side)
    # NOTA: como no pegaste cómo llamas a Cuescore, te dejo el esqueleto:
    #
    # import requests
    # api_key = os.environ.get("CUESCORE_API_KEY")
    # r = requests.get("URL_DE_CUESCORE", headers={"Authorization": api_key}, params={...})
    # return jsonify(r.json())

    return jsonify({
        "ok": True,
        "message": "Backend autorizado. Aquí llamas a Cuescore.",
        "playerId": player_id
    })

if __name__ == '__main__':
    with app.app_context():
        print(f"--- Conectado a base de datos en: {app.config['SQLALCHEMY_DATABASE_URI']} ---")
        db.create_all()

        if not Usuario.query.filter_by(rol='admin').first():
            db.session.add(Usuario(nombre="Diego Rey", correo="admin@poolroom.com", contrasena=generate_password_hash("admin123"), rol="admin", estado="activo"))
            db.session.commit()

    app.run(host='0.0.0.0', port=5005, debug=True)