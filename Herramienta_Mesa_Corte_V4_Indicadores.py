"""
Herramienta de ingeniería de control: mesa de corte automática.
Examen Parcial I (Q4 2026) - Proyecto individual.

Dependencias: Python 3, SymPy y Tkinter (incluido con Python habitualmente).
Para ejecutar en Thonny: abrir el .py y presionar F5.

NOTA ACADÉMICA: revisa, comprende, prueba y adapta este código.
La bitácora debe explicar tu boceto, el uso de IA y tus pruebas reales.
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import sympy as sp

S = sp.symbols('s')

# -----------------------------------------------------------------------------
# NÚCLEO MATEMÁTICO: funciones independientes de la interfaz gráfica
# -----------------------------------------------------------------------------

def fraccion(tf):
    """Devuelve numerador y denominador polinómicos de una función racional."""
    num, den = sp.fraction(sp.cancel(tf))
    return sp.expand(num), sp.expand(den)


def serie(a, b):
    """Conexión en serie de dos funciones de transferencia: A(s)B(s)."""
    na, da = fraccion(a)
    nb, db = fraccion(b)
    return sp.cancel((na * nb) / (da * db))


def paralelo(a, b):
    """Conexión en paralelo con suma positiva: A(s)+B(s)."""
    na, da = fraccion(a)
    nb, db = fraccion(b)
    return sp.cancel((na * db + nb * da) / (da * db))


def retro_negativa(g, h):
    """Realimentación negativa: G(s)/(1+G(s)H(s))."""
    ng, dg = fraccion(g)
    nh, dh = fraccion(h)
    return sp.cancel((ng * dh) / (dg * dh + ng * nh))


def racional(x):
    """Transforma un dato decimal en un número racional exacto de SymPy."""
    return sp.Rational(str(x))


def calcular_modelo(datos):
    """Calcula etapas, dos rutas de reducción y funciones finales del sistema.

    Unidades de entrada: resistencias en kiloohmios y capacitancias en microfaradios.
    Km es la ganancia del motor; el polo fijo del modelo es s+5.
    """
    r1 = racional(datos['R1']) * 1000
    r2 = racional(datos['R2']) * 1000
    c = racional(datos['C']) / 1000000
    ra = racional(datos['Ra']) * 1000
    rf = racional(datos['Rf']) * 1000
    cf = racional(datos['Cf']) / 1000000
    rt_in = racional(datos['Rt_in']) * 1000
    rt_f = racional(datos['Rt_f']) * 1000
    km = racional(datos['Km'])

    kp = r2 / r1
    ki = 1 / (r1 * c)
    tau = rf * cf
    ganancia_filtro = rf / ra

    # El primer AO de cada etapa es inversor; el siguiente AO invierte otra vez.
    gc = paralelo(kp, ki / S)              # PI = Kp + Ki/s
    h2 = sp.cancel(ganancia_filtro / (1 + tau * S))
    h1 = sp.cancel(rt_f / rt_in)           # (-Rf/Rin)*(-1) = positivo
    g2 = km / (S + 5)                      # Motor, velocidad
    g3 = 1 / S                             # Integrador, posición

    # MÉTODO 1: reducción sucesiva por realimentación, serie y realimentación.
    g_interna = retro_negativa(g2, h1)
    g_directa = serie(serie(gc, g_interna), g3)
    t_pos = retro_negativa(g_directa, h2)
    t_vel = serie(S, t_pos)                # Ω(s) = s C(s)

    # MÉTODO 2: expresión obtenida directamente por las ecuaciones del diagrama.
    t_alterna = sp.cancel(
        (gc * g2 * g3) / (1 + g2 * h1 + gc * g2 * g3 * h2)
    )
    verificadas = (sp.cancel(t_pos - t_alterna) == 0)
    if not verificadas:
        raise ArithmeticError('La reducción por ambos métodos no coincide.')

    bloques = {
        'Gc(s)  - controlador PI': gc,
        'G2(s)  - motor': g2,
        'G3(s)  - integrador': g3,
        'H1(s)  - tacómetro': h1,
        'H2(s)  - sensor/filtro': h2,
        'Gint(s)  - lazo interno': g_interna,
        'Gdir(s)  - trayectoria directa': g_directa,
        'C(s)/R(s)  - posición': t_pos,
        'Omega(s)/R(s)  - velocidad': t_vel,
        '1  - ganancia unitaria': sp.Integer(1),
    }
    return {
        'Kp': kp, 'Ki': ki, 'Ti': sp.cancel(kp / ki),
        'tau': tau, 'Kf': ganancia_filtro,
        'H1': h1, 'Gc': gc, 'H2': h2,
        'G2': g2, 'G3': g3,
        'Gint': g_interna, 'Gdir': g_directa,
        'Tpos': t_pos, 'Tvel': t_vel,
        'valida': verificadas, 'bloques': bloques,
    }


def analizar(tf):
    """Calcula los coeficientes, raíces y ganancia en CC de una FT racional."""
    num, den = fraccion(tf)
    pn, pd = sp.Poly(num, S), sp.Poly(den, S)
    ceros = [complex(r) for r in sp.nroots(pn, maxsteps=300)] if pn.degree() > 0 else []
    polos = [complex(r) for r in sp.nroots(pd, maxsteps=300)] if pd.degree() > 0 else []
    kdc = sp.limit(tf, S, 0)
    estable = all(r.real < -1e-8 for r in polos)
    return {
        'numerador': num, 'denominador': den,
        'coef_n': pn.all_coeffs(), 'coef_d': pd.all_coeffs(),
        'ceros': ceros, 'polos': polos,
        'kdc': kdc, 'estable': estable,
    }


def raiz_a_texto(z):
    if abs(z.imag) < 1e-8:
        return f'{z.real:.6f}'
    signo = '+' if z.imag >= 0 else '-'
    return f'{z.real:.6f} {signo} {abs(z.imag):.6f}j'


def resumen_modelo(modelo):
    """Genera texto exportable de resultados y comprobaciones."""
    t = analizar(modelo['Tpos'])
    v = analizar(modelo['Tvel'])

    def titulo(s):
        return '\n' + s + '\n' + ('-' * max(36, len(s))) + '\n'

    salida = 'MESA DE CORTE AUTOMÁTICA - MODELO DE CONTROL\n'
    salida += 'Parámetros ingresados por el técnico y análisis matemático.\n'
    salida += titulo('1. MODELO DE LOS BLOQUES')
    for nombre, f in list(modelo['bloques'].items())[:5]:
        salida += f'{nombre}\n    {sp.sstr(f)}\n\n'
    salida += (f'Kp = {modelo["Kp"]}\nKi = {modelo["Ki"]} 1/s\n'
               f'Ti = {modelo["Ti"]} s\n'
               f'Ganancia CC filtro = {modelo["Kf"]}\n'
               f'Tau filtro = {modelo["tau"]} s\n')
    salida += titulo('2. REDUCCIÓN DE BLOQUES')
    salida += ('Regla de paralelo: Gc = Kp + Ki/s\n'
               'Lazo interno: Gint = G2 / (1 + G2*H1)\n'
               'Serie: Gdir = Gc * Gint * G3\n'
               'Lazo externo: Tpos = Gdir / (1 + Gdir*H2)\n'
               'Velocidad: Tvel = s*Tpos\n')
    salida += f'Reducción interna: {sp.sstr(modelo["Gint"])}\n'
    salida += f'Trayectoria directa: {sp.sstr(modelo["Gdir"])}\n'
    salida += titulo('3. FUNCIÓN DE TRANSFERENCIA C(s)/R(s)')
    salida += f'C(s)/R(s) = ({t["numerador"]}) / ({t["denominador"]})\n'
    salida += 'Coeficientes N(s), de mayor a menor grado: ' + str(t['coef_n']) + '\n'
    salida += 'Coeficientes D(s), de mayor a menor grado: ' + str(t['coef_d']) + '\n'
    salida += 'Ceros: ' + (', '.join(map(raiz_a_texto, t['ceros'])) or 'Ninguno') + '\n'
    salida += 'Polos: ' + (', '.join(map(raiz_a_texto, t['polos'])) or 'Ninguno') + '\n'
    salida += f'Ganancia en CC: {t["kdc"]}\n'
    salida += f'Estabilidad: {"Estable (todos los polos a la izquierda)" if t["estable"] else "Verificar: hay polos no estrictamente estables"}\n'
    salida += titulo('4. FUNCIÓN DE TRANSFERENCIA OMEGA(s)/R(s)')
    salida += f'Omega(s)/R(s) = ({v["numerador"]}) / ({v["denominador"]})\n'
    salida += 'Coeficientes N(s): ' + str(v['coef_n']) + '\n'
    salida += 'Coeficientes D(s): ' + str(v['coef_d']) + '\n'
    salida += titulo('5. VERIFICACIÓN INDEPENDIENTE')
    salida += f'¿Coinciden ambas reducciones?: {modelo["valida"]}\n'
    salida += 'La ganancia CC igual a 1 no demuestra por sí sola estabilidad.\n'
    return salida


def escalon_rk4(tf, duracion=None):
    """Simula la respuesta al escalón por RK4 en forma canónica controlable.

    Sólo requiere Python estándar y SymPy. No utiliza scipy, numpy ni matplotlib.
    El sistema se escribe como D(s)Y(s)=N(s)U(s), con condiciones iniciales cero.
    """
    num, den = fraccion(tf)
    pn, pd = sp.Poly(num, S), sp.Poly(den, S)
    n = pd.degree()
    if pn.degree() >= n:
        raise ValueError('Esta gráfica requiere un sistema estrictamente propio.')
    if n <= 0 or n > 8:
        raise ValueError('Orden no admitido para la gráfica.')

    coef_d = [float(pd.nth(i) / pd.LC()) for i in range(n)]
    coef_n = [float(pn.nth(i) / pd.LC()) for i in range(n)]
    polos = [complex(r) for r in sp.nroots(pd, maxsteps=300)]
    rapidez = max(abs(z) for z in polos)
    amortiguamiento = [abs(z.real) for z in polos if z.real < -1e-8]
    mas_lento = min(amortiguamiento) if amortiguamiento else 1.0
    tiempo_total = duracion if duracion is not None else min(60.0, max(8.0, 6.0 / mas_lento))
    pasos = max(1500, math.ceil(tiempo_total * rapidez / 0.10))
    if pasos > 30000:
        raise ValueError('Parámetros muy rígidos: no se puede graficar con precisión razonable.')

    dt = tiempo_total / pasos
    estado = [0.0] * n
    puntos = [(0.0, 0.0)]
    frecuencia_muestreo = max(1, pasos // 600)

    def pendiente(x):
        # x0'=x1, x1'=x2, ... , xn-1'=1-a0*x0-...-an-1*xn-1
        return x[1:] + [1.0 - sum(coef_d[j] * x[j] for j in range(n))]

    def suma(x, a, factor):
        return [x[i] + factor * a[i] for i in range(n)]

    for i in range(1, pasos + 1):
        k1 = pendiente(estado)
        k2 = pendiente(suma(estado, k1, dt / 2))
        k3 = pendiente(suma(estado, k2, dt / 2))
        k4 = pendiente(suma(estado, k3, dt))
        estado = [
            estado[j] + dt * (k1[j] + 2*k2[j] + 2*k3[j] + k4[j]) / 6
            for j in range(n)
        ]
        if not all(math.isfinite(v) and abs(v) < 1e50 for v in estado):
            raise ValueError('La respuesta diverge; revisá estabilidad y parámetros.')
        if i % frecuencia_muestreo == 0 or i == pasos:
            salida = sum(coef_n[j] * estado[j] for j in range(n))
            if not math.isfinite(salida):
                raise ValueError('La respuesta no tiene valores finitos.')
            puntos.append((i * dt, salida))
    return puntos



def indicadores_escalon(puntos, ganancia_cc, estable=True):
    """Extrae magnitudes del escalón ya calculado; no son mediciones de planta.

    El valor máximo se estima mediante interpolación parabólica local sobre
    las muestras RK4. Para ganancias CC no nulas y sistemas estables se mide
    el sobreimpulso respecto al valor final previsto matemáticamente.
    """
    if not puntos:
        return None
    if not all(math.isfinite(t) and math.isfinite(y) for t, y in puntos):
        raise ValueError('Hay datos de simulación no finitos.')
    signo = -1 if ganancia_cc < 0 else 1
    i_pico = max(range(len(puntos)), key=lambda i: signo * puntos[i][1])
    tiempo_pico, valor_pico = puntos[i_pico]
    # Ajuste de una parábola a tres puntos vecinos; mejora el pico registrado
    # cuando se muestra la gráfica con ~600-800 muestras.
    if 0 < i_pico < len(puntos) - 1:
        t0, y0 = puntos[i_pico - 1]
        t1, y1 = puntos[i_pico]
        t2, y2 = puntos[i_pico + 1]
        h1, h2 = t1 - t0, t2 - t1
        if h1 > 0 and h2 > 0 and abs(h1 - h2) < 1e-6 * max(h1, h2):
            v0, v1, v2 = signo*y0, signo*y1, signo*y2
            denominador = v0 - 2*v1 + v2
            if denominador < -1e-14:
                delta = 0.5 * (v0 - v2) / denominador
                if abs(delta) <= 1:
                    tiempo_pico = t1 + delta * h1
                    valor_pico = signo * (v1 - 0.25*(v0-v2)*delta)

    sobreimpulso = None
    advertencia = ''
    if not estable:
        advertencia = 'Sistema no asintóticamente estable: sobreimpulso estacionario no aplicable.'
    elif not math.isfinite(ganancia_cc) or abs(ganancia_cc) < 1e-12:
        advertencia = 'Ganancia CC nula o indefinida: sobreimpulso porcentual no aplicable.'
    else:
        sobreimpulso = max(0.0, signo * (valor_pico - ganancia_cc)
                              / abs(ganancia_cc) * 100.0)

    return {
        't_pico': tiempo_pico,
        'y_pico': valor_pico,
        'sobreimpulso': sobreimpulso,
        'ganancia_cc': ganancia_cc,
        'estable': estable,
        'advertencia': advertencia,
        'muestras': len(puntos),
        'duracion': puntos[-1][0],
    }


def texto_indicadores(indicadores):
    """Genera el mismo resumen que se ve en la pestaña y que se exporta."""
    if not indicadores:
        return 'La simulación del escalón no está disponible.\n'
    i = indicadores
    s = ('SIMULACIÓN DEL ESCALÓN UNITARIO (modelo; no mediciones físicas)\n'
         'Entrada: R(s) = 1/s, condiciones iniciales cero.\n'
         'Método numérico: Runge-Kutta de cuarto orden (RK4).\n'
         f'Valor pico de la posición: {i["y_pico"]:.6f}\n'
         f'Tiempo del pico: {i["t_pico"]:.4f} s\n'
         f'Ganancia en CC teórica: {i["ganancia_cc"]:.6f}\n'
         f'Duración simulada: {i["duracion"]:.4f} s\n'
         f'Cantidad de muestras visualizadas: {i["muestras"]}\n')
    if i['sobreimpulso'] is None:
        s += 'Sobreimpulso porcentual: no aplicable.\n'
    else:
        s += (f'Sobreimpulso: {i["sobreimpulso"]:.2f} %\n'
              'Cálculo: (valor_pico - valor_final) / |valor_final| x 100 % '
              '(con signo de la salida).\n')
    if i['advertencia']:
        s += 'Advertencia: ' + i['advertencia'] + '\n'
    return s

# =============================================================================
# INTERFAZ INTERACTIVA: adaptada al boceto manuscrito del estudiante.
# La columna derecha permanece fija al navegar por las pestañas.
# Selecciona bloques con clic; otro clic los deselecciona.
# Las operaciones sólo se aplican si corresponden a la topología física actual.
# =============================================================================

COLOR_FONDO = '#eef3f8'
COLOR_PANEL = '#ffffff'
COLOR_TEXTO = '#17324b'
COLOR_SEC = '#597185'
COLOR_AZUL = '#185a82'
COLOR_ACENTO = '#087a77'
COLOR_CONTORNO = '#d9e4ec'
COLOR_SELECCION = '#fff1c7'
COLOR_SEL_BORDE = '#d38b16'



# =============================================================================
# REDUCTOR VISUAL GUIADO POR TOPOLOGÍA
# El estudiante ELIGE bloques y operación. El programa verifica conexiones
# y sólo entonces aplica la regla, reemplaza los bloques y registra cada paso.
# =============================================================================

class ReductorVisual(tk.Tk):
    ENTRADAS = [
        ('R1', 'R₁', 'kΩ', '10', 'CONTROLADOR PI'),
        ('R2', 'R₂', 'kΩ', '10', 'CONTROLADOR PI'),
        ('C', 'C', 'µF', '50', 'CONTROLADOR PI'),
        ('Ra', 'Rₐ', 'kΩ', '10', 'FILTRO DE POSICIÓN'),
        ('Rf', 'Rf', 'kΩ', '10', 'FILTRO DE POSICIÓN'),
        ('Cf', 'Cf', 'µF', '10', 'FILTRO DE POSICIÓN'),
        ('Rt_in', 'Rin', 'kΩ', '20', 'TACÓMETRO'),
        ('Rt_f', 'Rf', 'kΩ', '10', 'TACÓMETRO'),
        ('Km', 'Km', '—', '10', 'MOTOR'),
    ]

    def __init__(self):
        super().__init__()
        self.title('Mesa de corte · Reducción de bloques paso a paso')
        self.geometry('1390x870')
        self.minsize(1090, 720)
        self.configure(bg=COLOR_FONDO)
        self.vars = {}
        self.modelo = None
        self.nodos = {}
        self.cadena = []
        self.h2_activo = True
        self.seleccion = []
        self.registros = []
        self.pila_deshacer = []
        self.contador = 0
        self.terminado = False
        self.regla_elegida = None
        self.puntos_grafica = []
        self.indicadores = None
        self.error_grafica = ''
        self.resumen_exportable = ''
        self.inicializar_estilos()
        self.construir_interfaz()
        self.calcular()

    def inicializar_estilos(self):
        st = ttk.Style(self)
        if 'clam' in st.theme_names():
            st.theme_use('clam')
        st.configure('TNotebook.Tab', padding=(13, 10), font=('Segoe UI', 10, 'bold'))
        st.configure('Primary.TButton', padding=(10, 7),
                     background=COLOR_ACENTO, foreground='white',
                     font=('Segoe UI', 9, 'bold'))
        st.map('Primary.TButton', background=[('active', '#056a65')])
        st.configure('Second.TButton', padding=(9, 7), font=('Segoe UI', 9))

    @staticmethod
    def etiqueta(parent, texto, tam=10, negrita=False, color=COLOR_TEXTO, fondo=COLOR_PANEL, **kw):
        return tk.Label(parent, text=texto, bg=fondo, fg=color,
                        font=('Segoe UI', tam, 'bold' if negrita else 'normal'), **kw)

    @staticmethod
    def caja_texto(parent, height=10):
        frame = tk.Frame(parent, bg=COLOR_PANEL)
        text = tk.Text(frame, bg='#f7fbfd', fg=COLOR_TEXTO, wrap='word',
                       font=('Consolas', 10), relief='flat', padx=12, pady=9,
                       height=height)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scroll.set, state='disabled')
        scroll.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)
        return frame, text

    @staticmethod
    def colocar(widget, contenido):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('end', contenido)
        widget.configure(state='disabled')
        widget.see('end')

    def construir_interfaz(self):
        cabecera = tk.Frame(self, bg=COLOR_TEXTO, height=76)
        cabecera.pack(fill='x')
        cabecera.pack_propagate(False)
        self.etiqueta(cabecera, 'MESA DE CORTE  /  REDUCTOR DE DIAGRAMAS',
                      16, True, '#ffffff', COLOR_TEXTO).pack(anchor='w', padx=20, pady=(10, 0))
        self.etiqueta(cabecera, 'Seleccioná los bloques y la regla; el programa comprueba la conexión y explica cada operación.',
                      9, False, '#c8dfec', COLOR_TEXTO).pack(anchor='w', padx=20, pady=(2, 0))

        self.estado = self.etiqueta(self, 'Preparando...', 9, fondo='#dceef0', anchor='w', padx=12, pady=7)
        self.estado.pack(fill='x', side='bottom')

        marco = tk.Frame(self, bg=COLOR_FONDO)
        marco.pack(fill='both', expand=True, padx=12, pady=10)
        marco.grid_columnconfigure(0, weight=1)
        marco.grid_columnconfigure(1, minsize=320)
        marco.grid_rowconfigure(0, weight=1)
        izquierda = tk.Frame(marco, bg=COLOR_PANEL, highlightbackground=COLOR_CONTORNO, highlightthickness=1)
        izquierda.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        derecha = tk.Frame(marco, bg=COLOR_PANEL, width=315,
                           highlightbackground=COLOR_CONTORNO, highlightthickness=1)
        derecha.grid(row=0, column=1, sticky='ns')
        derecha.grid_propagate(False)
        self.sidebar(derecha)

        self.pestanas = ttk.Notebook(izquierda)
        self.pestanas.pack(fill='both', expand=True, padx=7, pady=7)
        self.tab_diagrama = tk.Frame(self.pestanas, bg=COLOR_PANEL)
        self.tab_historial = tk.Frame(self.pestanas, bg=COLOR_PANEL)
        self.tab_resultados = tk.Frame(self.pestanas, bg=COLOR_PANEL)
        self.tab_escalon = tk.Frame(self.pestanas, bg=COLOR_PANEL)
        self.tab_ayuda = tk.Frame(self.pestanas, bg=COLOR_PANEL)
        for tab, name in [
            (self.tab_diagrama, 'Reducir bloques'),
            (self.tab_historial, 'Historial de pasos'),
            (self.tab_resultados, 'Resultados'),
            (self.tab_escalon, 'Respuesta al escalón'),
            (self.tab_ayuda, 'Cómo usar'),
        ]:
            self.pestanas.add(tab, text=name)
        self.pestanas.bind('<<NotebookTabChanged>>', self.cambiar_pestana)
        self.pestaña_reduccion()
        self.pestaña_historial()
        self.pestaña_resultados()
        self.pestaña_escalon()
        self.pestaña_ayuda()

    def sidebar(self, padre):
        self.etiqueta(padre, 'ENTRADAS DEL TÉCNICO', 12, True).pack(anchor='w', padx=14, pady=(13, 2))
        self.etiqueta(padre, 'Siempre visibles · kΩ y µF', 9, color=COLOR_SEC).pack(anchor='w', padx=14)
        cont = tk.Frame(padre, bg=COLOR_PANEL)
        cont.pack(fill='both', expand=True, padx=9)
        canvas = tk.Canvas(cont, bg=COLOR_PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(cont, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        interior = tk.Frame(canvas, bg=COLOR_PANEL)
        win = canvas.create_window((0, 0), window=interior, anchor='nw')
        interior.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(win, width=e.width))
        grupo_anterior = None
        for clave, nombre, unidad, valor, grupo in self.ENTRADAS:
            if grupo != grupo_anterior:
                self.etiqueta(interior, grupo, 9, True, COLOR_AZUL).pack(
                    anchor='w', padx=6, pady=(11 if grupo_anterior else 4, 4))
                grupo_anterior = grupo
            fila = tk.Frame(interior, bg=COLOR_PANEL)
            fila.pack(fill='x', padx=7, pady=2)
            self.etiqueta(fila, nombre).pack(side='left')
            self.etiqueta(fila, unidad, 9, color=COLOR_SEC).pack(side='right')
            v = tk.StringVar(value=valor)
            self.vars[clave] = v
            e = tk.Entry(fila, textvariable=v, width=12, justify='right',
                         bg='#f6fafc', relief='solid', bd=1,
                         font=('Consolas', 10))
            e.pack(side='right', padx=8, ipady=3)
            e.bind('<Return>', lambda evt: self.calcular())

        tk.Frame(padre, height=1, bg=COLOR_CONTORNO).pack(fill='x', padx=12, pady=(8, 9))
        ttk.Button(padre, text='CALCULAR Y REINICIAR REDUCCIÓN', style='Primary.TButton',
                   command=self.calcular).pack(fill='x', padx=11, pady=(0, 6))
        ttk.Button(padre, text='Restaurar valores d = 0', command=self.restaurar).pack(fill='x', padx=11, pady=(0, 6))
        ttk.Button(padre, text='Exportar informe y registro .txt', command=self.exportar).pack(
            fill='x', padx=11, pady=(0, 12))
        self.referencia = self.etiqueta(padre, 'Parámetros personales: d = 0', 9,
                                       color='#0b5957', fondo='#e8f4f3',
                                       wraplength=280, justify='left', padx=10, pady=9)
        self.referencia.pack(fill='x', padx=11, pady=(0, 11))

    def pestaña_reduccion(self):
        self.etiqueta(self.tab_diagrama, 'DIAGRAMA QUE SE SIMPLIFICA CON CADA OPERACIÓN',
                      11, True).pack(anchor='w', padx=13, pady=(12, 3))
        self.etiqueta(self.tab_diagrama, 'Clic = seleccionar; segundo clic = quitar. Los bloques desaparecen al reducirse y nace un equivalente.',
                      9, color=COLOR_SEC).pack(anchor='w', padx=13)
        self.canvas = tk.Canvas(self.tab_diagrama, bg='#fbfdff', height=330,
                                highlightthickness=1, highlightbackground=COLOR_CONTORNO)
        self.canvas.pack(fill='both', expand=True, padx=12, pady=(8, 5))
        self.canvas.bind('<Button-1>', self.clic_bloque)
        self.canvas.bind('<Configure>', self.dibujar)
        barra = tk.Frame(self.tab_diagrama, bg=COLOR_PANEL)
        barra.pack(fill='x', padx=10, pady=(2, 5))
        for codigo, titulo in [('paralelo','PARALELO  +'),('serie','SERIE  ×'),
                               ('feedback','REALIMENTACIÓN  −')]:
            ttk.Button(barra, text=titulo, style='Primary.TButton' if codigo == 'feedback' else 'Second.TButton',
                       command=lambda op=codigo: self.elegir_regla(op)).pack(side='left', padx=3)
        ttk.Button(barra, text='APLICAR', style='Primary.TButton',
                   command=self.aplicar_regla).pack(side='left', padx=(7, 3))
        ttk.Button(barra, text='Deshacer', command=self.deshacer).pack(side='right', padx=4)
        ttk.Button(barra, text='Reiniciar', command=self.reiniciar_reduccion).pack(side='right', padx=4)
        ttk.Button(barra, text='Quitar selección', command=self.quitar_seleccion).pack(side='right', padx=4)

        self.etiqueta(self.tab_diagrama, 'CONSOLA MATEMÁTICA  ·  regla, sustitución, resultado e historial',
                      10, True).pack(anchor='w', padx=13, pady=(4, 1))
        consola_f, self.consola = self.caja_texto(self.tab_diagrama, height=10)
        consola_f.pack(fill='both', expand=False, padx=12, pady=(2, 10))

    def pestaña_historial(self):
        self.etiqueta(self.tab_historial, 'BITÁCORA COMPLETA DE LAS REDUCCIONES QUE REALIZASTE',
                      11, True).pack(anchor='w', padx=14, pady=(13, 5))
        frame, self.historial_ui = self.caja_texto(self.tab_historial, 27)
        frame.pack(fill='both', expand=True, padx=12, pady=(5, 12))

    def pestaña_resultados(self):
        self.etiqueta(self.tab_resultados, 'RESULTADOS DEL MODELO Y VERIFICACIÓN SIMBÓLICA',
                      11, True).pack(anchor='w', padx=14, pady=(13, 5))
        frame, self.resultados_ui = self.caja_texto(self.tab_resultados, 28)
        frame.pack(fill='both', expand=True, padx=12, pady=(5, 12))

    def pestaña_escalon(self):
        self.etiqueta(self.tab_escalon, 'RESPUESTA AL ESCALÓN UNITARIO',
                      11, True).pack(anchor='w', padx=14, pady=(13, 5))
        self.etiqueta(self.tab_escalon, 'Simulación por Runge–Kutta 4; se actualiza al modificar componentes y calcular.',
                      9, color=COLOR_SEC).pack(anchor='w', padx=14)
        self.grafica = tk.Canvas(self.tab_escalon, bg='#fbfdff', highlightthickness=1,
                                 highlightbackground=COLOR_CONTORNO)
        self.grafica.pack(fill='both', expand=True, padx=15, pady=(10, 6))
        self.grafica.bind('<Configure>', self.dibujar_grafica)
        # Métricas visibles bajo la curva. Se mantienen dentro de esta pestaña.
        datos_frame = tk.Frame(self.tab_escalon, bg=COLOR_PANEL)
        datos_frame.pack(fill='x', padx=15, pady=(2, 5))
        self.etiquetas_metricas = {}
        campos = [
            ('pico', 'POSICIÓN MÁXIMA'),
            ('tiempo', 'TIEMPO DEL PICO'),
            ('sobreimpulso', 'SOBREIMPULSO'),
        ]
        for col, (clave, titulo) in enumerate(campos):
            datos_frame.grid_columnconfigure(col, weight=1, uniform='metricas')
            celda = tk.Frame(datos_frame, bg='#edf5f7', highlightbackground=COLOR_CONTORNO,
                             highlightthickness=1)
            celda.grid(row=0, column=col, padx=4, sticky='ew')
            self.etiqueta(celda, titulo, 8, True, color=COLOR_SEC, fondo='#edf5f7').pack(
                anchor='w', padx=10, pady=(7, 1))
            valor = self.etiqueta(celda, '—', 15, True, color=COLOR_ACENTO, fondo='#edf5f7')
            valor.pack(anchor='w', padx=10, pady=(0, 7))
            self.etiquetas_metricas[clave] = valor
        self.leyenda = self.etiqueta(self.tab_escalon, 'Gráfica del modelo.', 9, color=COLOR_SEC)
        self.leyenda.pack(anchor='w', padx=15, pady=(0, 4))
        self.etiqueta(self.tab_escalon,
                      'Datos calculados de la función de transferencia; no son mediciones del equipo físico.',
                      9, color=COLOR_SEC).pack(anchor='w', padx=15, pady=(0, 9))

    def pestaña_ayuda(self):
        frame, ayuda = self.caja_texto(self.tab_ayuda, 28)
        frame.pack(fill='both', expand=True, padx=12, pady=12)
        self.colocar(ayuda,
            'REDUCCIÓN INTERACTIVA DEL SISTEMA DEL EXAMEN\n\n'
            '1. El técnico define componentes en el PANEL DERECHO (siempre visible).\n'
            '   Presioná CALCULAR para reconstruir el sistema con nuevos valores.\n\n'
            '2. En Reducir bloques, tocá con el mouse los bloques que querés operar.\n'
            '   Un segundo clic deselecciona el mismo bloque.\n\n'
            '3. Podés elegir la regla PRIMERO, marcar bloques y pulsar APLICAR.\n'
            '   O podés marcar los bloques primero y después presionar la operación.\n'
            '   El programa NO inventa una conexión ni permite aplicar una regla que\n'
            '   contradiga la topología actual. Te muestra el motivo en consola.\n\n'
            '4. Las reglas son:\n'
            '   PARALELO: G_eq = A+B (dos ramas con misma entrada/salida).\n'
            '   SERIE: G_eq = A*B*... (2 o más tramos consecutivos).\n'
            '   RETROALIM. NEGATIVA: G_eq = G/(1+G*H).\n'
            '   No confundás este paralelo de bloques con resistencias en paralelo.\n\n'
            '5. Una secuencia correcta para esta figura:\n'
            '   a) Kp y Ki/s → paralelo → controlador equivalente X01.\n'
            '   b) G2 y H1 → realimentación negativa → lazo interno X02.\n'
            '   c) X01, X02 y G3 → serie → trayectoria directa X03.\n'
            '   d) X03 y H2 → realimentación negativa → C(s)/R(s).\n'
            '   También podés asociar tramos EN SERIE de dos en dos.\n\n'
            '6. La consola muestra selección, regla, datos, sustitución y resultado.\n'
            '   La pestaña Historial conserva todos los pasos.\n'
            '   Deshacer revierte una reducción; Reiniciar repone todos los bloques.\n\n'
            '7. RESULTADOS calcula C/R, Omega/R, polos, ceros, coeficientes y\n'
            '   ganancia en CC, independientemente de que hayas completado el juego.\n'
            '   La pestaña ESCALÓN sólo se ve cuando la abrís.\n'
            '   Allí se muestran posición pico, tiempo de pico y sobreimpulso.\n'
            '   Son resultados NUMÉRICOS de la simulación RK4, no mediciones.\n'
            '   Exportar incluye esos indicadores y las muestras (tiempo, posición).\n\n'
            '8. Esta herramienta implementa las conexiones de la FIGURA 1.\n'
            '   No pretende interpretar automáticamente diagramas arbitrarios.\n'
            '   Los bloques originales no desaparecen matemáticamente: su producto o\n'
            '   suma se conserva dentro de cada nuevo bloque equivalente.\n\n'
            'DECLARACIÓN DE IA\n'
            '   Esta implementación de Python fue asistida por IA. El boceto de\n'
            '   interfaz y las deducciones manuales son trabajo del estudiante;\n'
            '   deben explicarse, verificarse y documentarse en la bitácora.\n')

    def cambiar_pestana(self, event=None):
        if self.pestanas.select() == str(self.tab_diagrama):
            self.after_idle(self.dibujar)
        if self.pestanas.select() == str(self.tab_escalon):
            self.after_idle(self.dibujar_grafica)

    def leer_parametros(self):
        datos = {}
        for key, name, unit, default, group in self.ENTRADAS:
            raw = self.vars[key].get().strip().replace(',', '.')
            try:
                num = float(raw)
            except ValueError:
                raise ValueError(f'{group} · {name}: ingresá un número válido.')
            if not math.isfinite(num) or not (1e-10 <= num <= 1e10):
                raise ValueError(f'{group} · {name}: valor positivo y finito requerido.')
            datos[key] = num
        return datos

    def calcular(self):
        try:
            datos = self.leer_parametros()
            modelo = calcular_modelo(datos)
            informe = resumen_modelo(modelo)
            try:
                puntos = escalon_rk4(modelo['Tpos'])
                error = ''
            except Exception as exc:
                puntos = []
                error = str(exc)
        except Exception as exc:
            messagebox.showerror('Parámetros incorrectos', str(exc))
            return False
        # Resultados de la misma simulación que dibuja la gráfica.
        if puntos:
            analisis = analizar(modelo['Tpos'])
            try:
                ganancia = float(sp.N(analisis['kdc']))
                indicadores = indicadores_escalon(puntos, ganancia, analisis['estable'])
            except (TypeError, ValueError, OverflowError):
                indicadores = indicadores_escalon(puntos, float('nan'), False)
        else:
            indicadores = None
        self.modelo = modelo
        self.indicadores = indicadores
        # Actualizar métricas aunque la pestaña Escalón todavía no esté visible.
        if indicadores:
            self.etiquetas_metricas['pico'].configure(text=f'{indicadores["y_pico"]:.4f}')
            self.etiquetas_metricas['tiempo'].configure(text=f'{indicadores["t_pico"]:.3f} s')
            sobre = indicadores['sobreimpulso']
            self.etiquetas_metricas['sobreimpulso'].configure(
                text='No aplica' if sobre is None else f'{sobre:.2f} %')
        else:
            for etiqueta in self.etiquetas_metricas.values():
                etiqueta.configure(text='—')
        self.resumen_exportable = informe
        self.puntos_grafica = puntos
        self.error_grafica = error
        self.colocar(self.resultados_ui, informe)
        self.reiniciar_reduccion()
        es_d0 = all(datos[k] == float(default) for k, _, _, default, _ in self.ENTRADAS)
        self.referencia.configure(text=('Parámetros d=0 · modelo coincide con la Parte B.'
                                      if es_d0 else
                                      'Parámetros modificados · modelo recalculado.'),
                                 fg='#0b5957' if es_d0 else '#805526')
        self.estado.configure(text='✓ Modelo calculado y verificado por dos rutas · ' +
                              ('Escalón disponible' if puntos else 'No se pudo graficar el escalón'))
        self.dibujar_grafica()
        return True

    def reiniciar_reduccion(self):
        if self.modelo is None:
            return
        m = self.modelo
        self.nodos = {
            'Kp': {'nombre':'Kp', 'tf':m['Kp']},
            'Ki': {'nombre':'Ki/s', 'tf':m['Ki']/S},
            'G2': {'nombre':'G₂(s)', 'tf':m['G2']},
            'H1': {'nombre':'H₁', 'tf':m['H1']},
            'G3': {'nombre':'G₃(s)', 'tf':m['G3']},
            'H2': {'nombre':'H₂(s)', 'tf':m['H2']},
        }
        self.cadena = [
            {'tipo':'pi','hijos':['Kp','Ki']},
            {'tipo':'interna','hijos':['G2','H1']},
            {'tipo':'bloque','id':'G3'},
        ]
        self.h2_activo = True
        self.terminado = False
        self.regla_elegida = None
        self.seleccion = []
        self.registros = []
        self.pila_deshacer = []
        self.contador = 0
        self.registrar('INICIO · Se conserva la topología original del examen.\n'
                       'Elegí bloques físicamente conectados y seleccioná la regla correcta.\n'
                       'Sugerencia: Kp + Ki/s → PARALELO. Después G₂ y H₁ → REALIMENTACIÓN −.')
        self.dibujar()

    def nombres_activos(self):
        claves = []
        for grupo in self.cadena:
            if grupo['tipo'] == 'bloque':
                claves.append(grupo['id'])
            else:
                claves.extend(grupo['hijos'])
        if self.h2_activo:
            claves.append('H2')
        return claves

    def alternar(self, clave):
        if clave not in self.nombres_activos():
            return
        if clave in self.seleccion:
            self.seleccion.remove(clave)
        else:
            self.seleccion.append(clave)
        nombres = ', '.join(self.nodos[k]['nombre'] for k in self.seleccion) or 'ninguno'
        self.estado.configure(text='Selección: '+nombres+'  ·  Elegí una operación.')
        self.dibujar()

    def quitar_seleccion(self):
        self.seleccion = []
        self.dibujar()
        self.estado.configure(text='Selección eliminada.')

    def registrar(self, mensaje):
        self.registros.append(mensaje)
        self.colocar(self.consola, mensaje)
        self.colocar(self.historial_ui, ('\n\n' + '─' * 66 + '\n\n').join(self.registros))

    def rechazar(self, causa):
        elegido = ', '.join(self.nodos[k]['nombre'] for k in self.seleccion) or 'nada'
        mensaje = ('OPERACIÓN NO APLICABLE AL DIAGRAMA ACTUAL\n'
                   f'Se seleccionó: {elegido}\n'
                   f'Motivo: {causa}\n'
                   'No se cambió ningún bloque. Probá otra selección u otra regla.')
        self.registrar(mensaje)
        self.estado.configure(text='⚠ Operación no aplicable; revisá la consola.')

    def obtener_operacion(self, tipo):
        """Comprueba que la selección sea una subestructura válida del diagrama.

        Devuelve (claves en orden físico, índice de inicio, cantidad, nombre regla).
        Para paralelo y lazos la topología fija exactamente quién es G y quién H.
        """
        elegidos = set(self.seleccion)
        if len(elegidos) < 2:
            raise ValueError('Seleccioná al menos dos bloques.')
        if tipo == 'paralelo':
            for i,g in enumerate(self.cadena):
                if g['tipo']=='pi' and elegidos==set(g['hijos']):
                    return g['hijos'], i, 1, 'PARALELO'
            raise ValueError('Sólo Kp y Ki/s comparten entrada y salida en paralelo en esta etapa. '
                             'No se pueden sumar bloques que estén conectados en serie.')
        if tipo == 'feedback':
            for i,g in enumerate(self.cadena):
                if g['tipo']=='interna' and elegidos==set(g['hijos']):
                    return g['hijos'], i, 1, 'REALIMENTACIÓN INTERNA NEGATIVA'
            if (len(self.cadena)==1 and self.cadena[0]['tipo']=='bloque'
                and self.h2_activo and elegidos=={self.cadena[0]['id'],'H2'}):
                return [self.cadena[0]['id'],'H2'], 0, 1, 'REALIMENTACIÓN EXTERNA NEGATIVA'
            raise ValueError('Sólo G₂/H₁ forman el lazo interno; el lazo externo '
                             'requiere primero un único bloque de trayectoria directa y H₂.')
        if tipo == 'serie':
            if any(g['tipo']!='bloque' for g in self.cadena):
                # Si hay PI o lazo interno sin resolver, los bloques expuestos
                # tienen puntos de suma/ramificación que impiden fusionarlos.
                raise ValueError('Primero reducí el paralelo Kp/Ki y el lazo G₂/H₁. '
                                 'Así no desaparecen puntos de suma o ramificación.')
            cadena_ids = [g['id'] for g in self.cadena]
            if not elegidos.issubset(set(cadena_ids)):
                raise ValueError('Para serie seleccioná sólo bloques de la trayectoria directa.')
            indices = [i for i, key in enumerate(cadena_ids) if key in elegidos]
            if len(indices)>=2 and indices == list(range(min(indices), max(indices)+1)):
                return [cadena_ids[i] for i in indices], min(indices), len(indices), 'SERIE'
            raise ValueError('Serie requiere 2 o más bloques consecutivos, sin saltar bloques intermedios.')
        raise ValueError('Operación desconocida.')

    def elegir_regla(self, tipo):
        """Permite elegir una regla antes de los bloques o aplicarla tras seleccionarlos."""
        self.regla_elegida = tipo
        nombres = {'serie':'SERIE', 'paralelo':'PARALELO',
                   'feedback':'REALIMENTACIÓN NEGATIVA'}
        if len(self.seleccion) >= 2:
            return self.operar(tipo)
        self.estado.configure(text=f'Regla elegida: {nombres[tipo]}. '
                              'Seleccioná los bloques y presioná APLICAR.')
        return None

    def aplicar_regla(self):
        if self.regla_elegida is None:
            self.rechazar('Primero elegí una regla: Serie, Paralelo o Realimentación negativa.')
            return False
        return self.operar(self.regla_elegida)

    def operar(self, tipo):
        if self.terminado:
            self.rechazar('Ya completaste C(s)/R(s). Usá Reiniciar o Deshacer para volver a reducir.')
            return False
        try:
            claves, pos, n_grupos, regla = self.obtener_operacion(tipo)
            funciones = [self.nodos[k]['tf'] for k in claves]
            if tipo == 'paralelo':
                fx = paralelo(funciones[0], funciones[1])
                formula = 'G_eq(s) = A(s) + B(s)'
                sustitucion = f'G_eq(s) = ({sp.sstr(funciones[0])}) + ({sp.sstr(funciones[1])})'
            elif tipo == 'serie':
                fx = sp.Integer(1)
                for f in funciones:
                    fx = serie(fx, f)
                formula = 'G_eq(s) = A(s) × B(s)' + (' × ...' if len(claves)>2 else '')
                sustitucion = 'G_eq(s) = ' + ' × '.join(f'({sp.sstr(f)})' for f in funciones)
            else:
                fx = retro_negativa(funciones[0], funciones[1])
                formula = 'G_eq(s) = G(s) / [1 + G(s)H(s)]'
                sustitucion = (f'G_eq(s) = ({sp.sstr(funciones[0])}) / '
                                f'[1 + ({sp.sstr(funciones[0])})({sp.sstr(funciones[1])})]')
            numerador, denominador = fraccion(fx)
        except ValueError as exc:
            self.rechazar(str(exc))
            return False
        except Exception as exc:
            self.rechazar('Error matemático: '+str(exc))
            return False

        # Crear la nueva etapa es transaccional: sólo modificar el grafo tras validar.
        copia = (
            [dict(g, **({'hijos':g['hijos'][:]} if 'hijos' in g else {})) for g in self.cadena],
            dict(self.nodos), self.h2_activo, self.terminado, self.contador,
            self.seleccion[:], self.registros[:]
        )
        self.pila_deshacer.append(copia)
        self.contador += 1
        etiqueta_nueva = f'X{self.contador:02d}'
        es_externo = tipo=='feedback' and claves[-1]=='H2'
        descripcion = ('C(s)/R(s) · sistema completo' if es_externo else
                       'Controlador PI equivalente' if tipo=='paralelo' else
                       'Lazo interno equivalente' if tipo=='feedback' else
                       'Tramo de trayectoria directa')
        self.nodos[etiqueta_nueva] = {'nombre': etiqueta_nueva, 'tf': fx,
                                     'descripcion': descripcion}
        self.cadena[pos:pos+n_grupos] = [{'tipo':'bloque', 'id':etiqueta_nueva}]
        if es_externo:
            self.h2_activo = False
            self.terminado = True
        self.seleccion = []
        self.regla_elegida = None
        nombres = ', '.join(self.nodos[k]['nombre'] for k in claves)
        compara = sp.cancel(fx - self.modelo['Tpos']) == 0 if es_externo else None
        paso = (f'PASO {self.contador:02d}  ·  {regla}\n'
                f'Bloques seleccionados: {nombres}\n'
                'Conexión: válida para la estructura actual del diagrama.\n\n'
                f'REGLA: {formula}\n\n'
                'DATOS:\n' + ''.join(f'  {chr(65+i)}(s) = {sp.sstr(f)}\n'
                                   for i,f in enumerate(funciones)) + '\n'
                f'SUSTITUCIÓN: {sustitucion}\n\n'
                f'RESULTADO: {etiqueta_nueva}(s) = {sp.sstr(fx)}\n'
                f'Numerador desarrollado: {numerador}\n'
                f'Denominador desarrollado: {denominador}\n'
                f'Nuevo bloque: {etiqueta_nueva} ({descripcion}).\n')
        if es_externo:
            paso += (f'\nCOMPROBACIÓN CON LA PARTE B: {compara}\n'
                     'Se ha obtenido la función C(s)/R(s) en lazo cerrado.\n')
        self.registrar(paso)
        self.dibujar()
        self.estado.configure(text=(f'✓ Paso {self.contador}: {etiqueta_nueva} reemplazó los bloques anteriores.'
                                     if not es_externo else
                                     '✓ Reducción terminada: C(s)/R(s), verificada con SymPy.'))
        return True

    def deshacer(self):
        if not self.pila_deshacer:
            self.estado.configure(text='No hay una reducción para deshacer.')
            return
        (self.cadena, self.nodos, self.h2_activo, self.terminado,
         self.contador, self.seleccion, self.registros) = self.pila_deshacer.pop()
        self.registrar('DESHACER · Se restauró el estado anterior. Podés elegir otra reducción.')
        self.dibujar()
        self.estado.configure(text='Se deshizo la última reducción.')

    def clic_bloque(self, event):
        etiquetas = self.canvas.gettags('current')
        clave = next((t.split(':',1)[1] for t in etiquetas if t.startswith('bloque:')), None)
        if clave:
            self.alternar(clave)

    def dibujar(self, event=None):
        if not hasattr(self, 'canvas') or self.modelo is None:
            return
        c = self.canvas
        c.delete('all')
        ancho, alto = max(c.winfo_width(), 200), max(c.winfo_height(), 140)
        escala = min(ancho/1080, alto/480)
        offx = (ancho-1080*escala)/2
        offy = (alto-480*escala)/2
        X = lambda z: offx+z*escala
        Y = lambda z: offy+z*escala
        F = lambda v: max(8, round(v*escala))

        def camino(*puntos, flecha=False, tono=COLOR_AZUL):
            c.create_line(*[X(v) if j%2==0 else Y(v) for j,v in enumerate(puntos)],
                          fill=tono, width=max(1.1, 1.9*escala),
                          arrow='last' if flecha else 'none')

        def bloque(clave, texto, x1,y1,x2,y2):
            marcado = clave in self.seleccion
            tags = ('bloque:'+clave, 'seleccionable')
            c.create_rectangle(X(x1),Y(y1),X(x2),Y(y2),
                               outline=COLOR_SEL_BORDE if marcado else COLOR_ACENTO,
                               fill=COLOR_SELECCION if marcado else '#e2f4f1',
                               width=2.5 if marcado else 1.6, tags=tags)
            c.create_text(X((x1+x2)/2),Y((y1+y2)/2),text=texto,
                          fill=COLOR_TEXTO,font=('Segoe UI', F(16),'bold'), tags=tags)
            if marcado:
                indice = self.seleccion.index(clave)+1
                c.create_oval(X(x1-10),Y(y1-12),X(x1+14),Y(y1+12),
                              fill=COLOR_SEL_BORDE,outline='white',tags=tags)
                c.create_text(X(x1+2),Y(y1),text=str(indice),fill='white',
                              font=('Segoe UI',F(11),'bold'),tags=tags)

        def sumador(x,y,negativo=False):
            c.create_oval(X(x-13),Y(y-13),X(x+13),Y(y+13),
                          outline=COLOR_AZUL,fill='white',width=2)
            c.create_text(X(x-17),Y(y-17),text='+',fill=COLOR_ACENTO,
                          font=('Segoe UI',F(13),'bold'))
            if negativo:
                c.create_text(X(x-18),Y(y+16),text='−',fill='#b76137',
                              font=('Segoe UI',F(13),'bold'))

        centros = ({3:[245,535,855],2:[355,755],1:[555]}.get(len(self.cadena)))
        if centros is None:
            centros = [230+200*i for i in range(len(self.cadena))]
        y0 = 192
        anterior = 105
        c.create_text(X(20),Y(168),text='R(s)',anchor='w',
                      font=('Segoe UI',F(15),'bold'),fill=COLOR_TEXTO)
        if self.h2_activo:
            sumador(95,y0,negativo=True)
        for centro, grp in zip(centros, self.cadena):
            tipo = grp['tipo']
            if tipo=='pi':
                camino(anterior,y0,centro-112,y0)
                camino(centro-112,y0,centro-112,116,centro-55,116, flecha=True)
                camino(centro-112,y0,centro-112,263,centro-55,263, flecha=True)
                bloque('Kp','Kp',centro-55,93,centro+45,139)
                bloque('Ki','Ki/s',centro-55,239,centro+45,285)
                camino(centro+45,116,centro+90,116,centro+90,y0-14)
                camino(centro+45,263,centro+90,263,centro+90,y0+14)
                sumador(centro+90,y0)
                anterior = centro+103
            elif tipo=='interna':
                camino(anterior,y0,centro-95,y0)
                sumador(centro-84,y0,negativo=True)
                camino(centro-71,y0,centro-42,y0)
                bloque('G2','G₂(s)',centro-42,168,centro+60,216)
                camino(centro+60,y0,centro+104,y0)
                camino(centro+86,y0,centro+86,336,centro+40,336)
                bloque('H1','H₁',centro-38,313,centro+40,358)
                camino(centro-38,336,centro-84,336,centro-84,y0+14, flecha=True)
                anterior = centro+104
            else:
                clave = grp['id']
                camino(anterior,y0,centro-74,y0, flecha=True)
                nom = self.nodos[clave]['nombre']
                bloque(clave,nom,centro-74,166,centro+74,218)
                anterior = centro+74
        camino(anterior,y0,1002,y0, flecha=True)
        c.create_text(X(1018),Y(164),text='C(s)',anchor='e',
                      font=('Segoe UI',F(15),'bold'),fill=COLOR_TEXTO)
        if self.h2_activo:
            camino(969,y0,969,423,615,423)
            bloque('H2','H₂(s)',490,400,615,446)
            camino(490,423,95,423,95,y0+13, flecha=True)
            c.create_text(X(766),Y(392),text='Lazo externo de posición',
                          font=('Segoe UI',F(12)),fill=COLOR_SEC)
        else:
            c.create_text(X(535),Y(405),text='REDUCCIÓN COMPLETA ✓  ·  C(s)/R(s)',
                          fill=COLOR_ACENTO,font=('Segoe UI',F(16),'bold'))
        if not self.terminado:
            c.create_text(X(538),Y(30),text='SELECCIÓN ACTUAL: '+(
                ', '.join(self.nodos[k]['nombre'] for k in self.seleccion) if self.seleccion else 'ninguna'),
                fill=COLOR_SEC,font=('Segoe UI',F(12),'bold'))
        c.tag_bind('seleccionable','<Enter>',lambda e: c.configure(cursor='hand2'))
        c.tag_bind('seleccionable','<Leave>',lambda e: c.configure(cursor='arrow'))

    def restaurar(self):
        for k, _, _, valor, _ in self.ENTRADAS:
            self.vars[k].set(valor)
        self.calcular()

    def exportar(self):
        if not self.modelo:
            return
        ruta = filedialog.asksaveasfilename(defaultextension='.txt',
                   initialfile='registro_mesa_corte.txt',
                   filetypes=[('Archivo de texto','*.txt')])
        if not ruta:
            return
        try:
            parametros = '\n'.join(f'{key} = {v.get()}' for key,v in self.vars.items())
            contenido = ('HERRAMIENTA PARA LA MESA DE CORTE\n'
                         'Parámetros (kΩ, µF salvo Km):\n'+parametros+'\n\n'+
                         self.resumen_exportable+'\n\n'+
                         texto_indicadores(self.indicadores)+'\n'+
                         'BITÁCORA DE REDUCCIÓN INTERACTIVA\n\n'+
                         ('\n\n'+'-'*66+'\n\n').join(self.registros)+'\n')
            if self.puntos_grafica:
                contenido += ('\nDATOS DE LA SIMULACIÓN RK4\n'
                              'Cada fila procede de la misma serie utilizada en la gráfica.\n'
                              'Tiempo (s)\tPosición normalizada\n')
                contenido += ''.join(f'{tiempo:.6f}\t{posicion:.9f}\n'
                                     for tiempo, posicion in self.puntos_grafica)
            with open(ruta,'w',encoding='utf-8') as fp:
                fp.write(contenido)
            self.estado.configure(text='Registro exportado: '+ruta)
        except OSError as exc:
            messagebox.showerror('Error al exportar',str(exc))

    def dibujar_grafica(self, event=None):
        if not hasattr(self, 'grafica') or self.modelo is None:
            return
        c = self.grafica
        c.delete('all')
        w,h = c.winfo_width(),c.winfo_height()
        if w<250 or h<170:
            return
        if not self.puntos_grafica:
            c.create_text(30,40,text='No disponible: '+self.error_grafica,
                          anchor='w',fill='#a34b39')
            self.leyenda.configure(text='La respuesta numérica no está disponible.')
            for etiqueta in self.etiquetas_metricas.values():
                etiqueta.configure(text='—')
            return
        pts=self.puntos_grafica
        if self.indicadores:
            i = self.indicadores
            self.etiquetas_metricas['pico'].configure(text=f'{i["y_pico"]:.4f}')
            self.etiquetas_metricas['tiempo'].configure(text=f'{i["t_pico"]:.3f} s')
            porcentaje = i['sobreimpulso']
            self.etiquetas_metricas['sobreimpulso'].configure(
                text='No aplica' if porcentaje is None else f'{porcentaje:.2f} %')
        izquierda,derecha,arriba,abajo=69,33,29,54
        aw,ah=w-izquierda-derecha,h-arriba-abajo
        cc=float(sp.N(sp.limit(self.modelo['Tpos'],S,0)))
        lo=min([0,cc]+[y for _,y in pts]); hi=max([0,cc]+[y for _,y in pts])
        rango=max(0.02,hi-lo)
        lo-=rango*0.10;hi+=rango*0.10
        total=pts[-1][0]
        xx=lambda t:izquierda+aw*t/total
        yy=lambda v:arriba+ah*(hi-v)/(hi-lo)
        for j in range(6):
            val=lo+(hi-lo)*j/5
            yg=yy(val)
            c.create_line(izquierda,yg,w-derecha,yg,fill='#e1ebf0')
            c.create_text(izquierda-9,yg,text=f'{val:.2f}',anchor='e',
                          fill=COLOR_SEC,font=('Segoe UI',9))
            t=total*j/5; xg=xx(t)
            c.create_line(xg,arriba,xg,h-abajo,fill='#edf2f5')
            c.create_text(xg,h-abajo+18,text=f'{t:.1f}',fill=COLOR_SEC,font=('Segoe UI',9))
        c.create_line(izquierda,arriba,izquierda,h-abajo,fill=COLOR_AZUL,width=1.5)
        c.create_line(izquierda,h-abajo,w-derecha,h-abajo,fill=COLOR_AZUL,width=1.5)
        c.create_line(izquierda,yy(cc),w-derecha,yy(cc),fill='#bb8145',dash=(5,4),width=2)
        xy=[]
        for t,y in pts:
            xy.extend([xx(t),yy(y)])
        if len(xy)>=4:
            c.create_line(*xy,fill=COLOR_ACENTO,width=2.5)
        # Identificar el primer máximo global sobre la misma curva calculada.
        if self.indicadores:
            pico_x = xx(self.indicadores['t_pico'])
            pico_y = yy(self.indicadores['y_pico'])
            c.create_line(pico_x, pico_y, pico_x, h-abajo,
                          fill='#c1842e', dash=(3, 5), width=1.3)
            c.create_oval(pico_x-5, pico_y-5, pico_x+5, pico_y+5,
                          fill='#c1842e', outline='#ffffff', width=1.2)
            etiqueta = f'Pico: {self.indicadores["y_pico"]:.4f}'
            x_etiqueta = min(max(pico_x + 9, izquierda+12), w-derecha-115)
            y_etiqueta = max(arriba+22, pico_y-16)
            c.create_text(x_etiqueta, y_etiqueta, text=etiqueta,
                          anchor='w', fill='#a46a1d', font=('Segoe UI',9,'bold'))
        c.create_text(izquierda+12,arriba+11,
                      text='— Posición       – – Valor estacionario',
                      anchor='w',fill=COLOR_SEC,font=('Segoe UI',10))
        c.create_text(w/2,h-17,text='Tiempo (s)',fill=COLOR_TEXTO,
                      font=('Segoe UI',10,'bold'))
        self.leyenda.configure(text=f'Escalón unitario · duración {total:.1f} s · ganancia CC {cc:.4f} · RK4')


if __name__ == '__main__':
    ReductorVisual().mainloop()
