# =====================================================================
# ASISTENTE VIRTUAL DE PELUQUERÍA
# Ventana (Tkinter) donde el usuario escribe una pregunta y la IA de
# Google (Gemini) responde usando la información de servicios.txt.
# =====================================================================

import os                          # para leer variables de entorno y trabajar con rutas de archivos
import threading                   # para ejecutar tareas en segundo plano (hilos)
import tkinter as tk               # librería para crear ventanas (viene incluida con Python)
from tkinter import scrolledtext   # cuadro de texto con barra de desplazamiento (scroll)

from dotenv import load_dotenv     # lee el archivo .env donde está guardada la clave API
from google import genai           # librería oficial para conectarse a Gemini
from google.genai import types     # clases para configurar la petición (por ejemplo, el contexto)

# ---------- 1. CONFIGURACIÓN ----------

# Carga el archivo .env: así la clave queda disponible como variable de entorno
# y NO hace falta escribirla dentro del código (por seguridad).
load_dotenv()

# Lee la variable API_KEY del .env. Si no existe, devuelve None.
API_KEY = os.getenv("API_KEY")

# Modelo de IA que vamos a usar
MODELO = "gemini-2.5-flash"  # he puesto este porque es el mas veloz de todos y para preguntas basicas es perfecto

# Si no hay clave, paramos el programa con un mensaje claro en vez de fallar más adelante
if not API_KEY:
    raise SystemExit("Falta API_KEY. Crea un archivo .env con: API_KEY=tu_clave")

# Construimos la ruta de servicios.txt partiendo de la carpeta donde está este script.
# __file__ = ruta de este archivo; abspath la hace completa; dirname se queda con la carpeta.
# Así funciona aunque ejecutes el programa desde otra carpeta.
RUTA_SERVICIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "servicios.txt")

# Abrimos servicios.txt y guardamos todo su texto en la variable CONTEXTO.
# encoding="utf-8" sirve para que se lean bien las tildes, la ñ y el símbolo €.
with open(RUTA_SERVICIOS, encoding="utf-8") as f:
    CONTEXTO = f.read()

# Este es el "prompt del sistema": las reglas de comportamiento + la información de la peluquería.
# Esto es el IN-CONTEXT LEARNING: no entrenamos el modelo, le damos la información
# directamente en el texto que le enviamos para que responda basándose en ella.
INSTRUCCIONES = (
    "Eres el asistente virtual de una peluquería. Responde en español, de forma "
    "amable, clara y breve. Usa ÚNICAMENTE la información de abajo. Si te preguntan "
    "algo que no aparece, di que no dispones de esa información y sugiere contactar "
    "con la peluquería. No inventes precios ni horarios.\n\n"
    "INFORMACIÓN DE LA PELUQUERÍA:\n" + CONTEXTO   # aquí se pega el contenido de servicios.txt
)

# Crea el "cliente": el objeto que nos conecta con Gemini usando nuestra clave
client = genai.Client(api_key=API_KEY)


# ---------- 2. LLAMADA A GEMINI + MANEJO DEL JSON ----------

def consultar_gemini(pregunta):
    """Envía la pregunta a Gemini y devuelve solo el texto de la respuesta."""
    try:
        # Enviamos la pregunta al modelo. Las reglas y el contexto van aparte,
        # en system_instruction, y la pregunta del usuario va en contents.
        respuesta = client.models.generate_content(
            model=MODELO,
            contents=pregunta,
            config=types.GenerateContentConfig(system_instruction=INSTRUCCIONES),
        )

        # La respuesta completa es un objeto grande (equivale a un JSON) con mucha
        # información: candidatos, tokens usados, etc. Lo convertimos a un
        # diccionario de Python para poder navegar por él como un JSON.
        datos = respuesta.model_dump(mode="json")

        # Navegamos por el JSON hasta llegar al texto:
        # candidates (lista de respuestas) -> [0] (la primera) -> content -> parts -> [0] -> text
        texto = datos["candidates"][0]["content"]["parts"][0]["text"]

        # Gemini escribe en Markdown (**negrita**), pero Tkinter no lo interpreta
        # y se verían los asteriscos. Los quitamos.
        return texto.replace("**", "")

    except (KeyError, IndexError, TypeError):
        # El JSON no tenía la estructura esperada (falta alguna clave o la lista está vacía)
        return "No he podido interpretar la respuesta del modelo."
    except Exception as e:
        # Cualquier otro fallo (sin internet, clave incorrecta, límite de uso...)
        return f"Error al conectar con Gemini: {e}"


# ---------- 3. INTERFAZ GRÁFICA (TKINTER) ----------

def escribir(texto, etiqueta=None):
    """Añade texto al final del chat. La etiqueta indica el color/estilo."""
    chat.config(state="normal")        # desbloquea el cuadro (bloqueado, no se puede modificar)
    chat.insert(tk.END, texto, etiqueta)  # inserta el texto al final con el estilo indicado
    chat.config(state="disabled")      # lo vuelve a bloquear para que el usuario no escriba en él
    chat.see(tk.END)                   # baja el scroll hasta el último mensaje


def enviar(event=None):
    """Se ejecuta al pulsar el botón 'Enviar' o la tecla Enter."""
    # Coge el texto escrito y quita espacios al principio y al final
    pregunta = entrada.get().strip()
    if not pregunta:                   # si está vacío, no hacemos nada
        return
    entrada.delete(0, tk.END)          # vacía el cuadro de escribir
    escribir(f"Tú: {pregunta}\n", "usuario")           # muestra la pregunta en azul
    boton.config(state="disabled")     # desactiva el botón para no enviar dos veces seguidas
    escribir("Asistente: escribiendo...\n", "espera")  # aviso mientras llega la respuesta

    # La llamada a Gemini tarda unos segundos. Si la hiciéramos aquí directamente,
    # la ventana se quedaría congelada. Por eso se ejecuta en un hilo aparte (en segundo plano).
    # daemon=True: el hilo se cierra solo si cerramos la ventana.
    threading.Thread(target=hilo_consulta, args=(pregunta,), daemon=True).start()


def hilo_consulta(pregunta):
    """Corre en segundo plano: pide la respuesta a Gemini y la entrega a la ventana."""
    texto = consultar_gemini(pregunta)
    # Tkinter solo permite modificar la ventana desde su hilo principal.
    # after(0, ...) le pide al hilo principal que ejecute mostrar_respuesta cuanto antes.
    ventana.after(0, mostrar_respuesta, texto)


def mostrar_respuesta(texto):
    """Quita el aviso 'escribiendo...' y muestra la respuesta de Gemini."""
    chat.config(state="normal")
    # Borra la línea "Asistente: escribiendo..." (la penúltima línea del chat)
    chat.delete("end-2l linestart", "end-1c")
    chat.config(state="disabled")
    escribir(f"Asistente: {texto}\n\n", "asistente")  # respuesta en verde
    boton.config(state="normal")       # reactiva el botón
    entrada.focus()                    # deja el cursor listo en el cuadro de escribir


def main():
    """Crea la ventana con todos sus elementos y la mantiene abierta."""
    # Estos elementos se declaran global para poder usarlos desde las funciones de arriba
    global ventana, chat, entrada, boton

    # Ventana principal
    ventana = tk.Tk()
    ventana.title("Asistente de Peluquería")   # texto de la barra de título
    ventana.geometry("640x520")                # tamaño: ancho x alto en píxeles

    # Área grande donde aparece la conversación (con scroll).
    # wrap=WORD: las líneas largas se cortan entre palabras, no a mitad de una.
    # state="disabled": el usuario no puede escribir en ella.
    chat = scrolledtext.ScrolledText(ventana, wrap=tk.WORD, state="disabled", font=("Arial", 11))
    chat.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)  # ocupa todo el espacio disponible

    # Estilos (etiquetas) para dar color a cada tipo de mensaje
    chat.tag_config("usuario", foreground="blue", font=("Arial", 11, "bold"))  # tus preguntas
    chat.tag_config("asistente", foreground="green")                           # respuestas de la IA
    chat.tag_config("espera", foreground="gray")                               # "escribiendo..."

    # Marco inferior que agrupa el cuadro de texto y el botón en la misma fila
    marco = tk.Frame(ventana)
    marco.pack(padx=10, pady=(0, 10), fill=tk.X)

    # Cuadro de una línea donde el usuario escribe la pregunta (a la izquierda, ocupa el sobrante)
    entrada = tk.Entry(marco, font=("Arial", 11))
    entrada.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
    entrada.bind("<Return>", enviar)   # al pulsar Enter se llama a enviar() igual que con el botón

    # Botón 'Enviar' (a la derecha). command=enviar: la función que se ejecuta al hacer clic.
    boton = tk.Button(marco, text="Enviar", command=enviar, bg="#0078d7", fg="white",
                      font=("Arial", 10, "bold"))
    boton.pack(side=tk.RIGHT, padx=(8, 0))

    # Mensaje de bienvenida
    escribir("Bienvenido al Asistente de Peluquería.\n"
             "Escribe tu pregunta abajo y presiona 'Enviar'.\n\n")
    entrada.focus()        # el cursor empieza dentro del cuadro de escribir

    # Arranca el bucle de la ventana: se queda abierta esperando clics y teclas hasta cerrarla
    ventana.mainloop()


# Solo ejecuta main() si lanzamos este archivo directamente (python asistente_gui.py).
# Si otro archivo lo importa, no se abre la ventana.
if __name__ == "__main__":
    main()
