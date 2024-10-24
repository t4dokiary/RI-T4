#LIBRERIAS
import os                               #Manipulaciones comunes de nombre de ruta
import sys
import re                               #Operaciones con expresiones regulares
from unicodedata import normalize       #Normalización de texto Unicode en forma compuesta o descompuesta (NFC o NFD)
import nltk                             #Procesamiento de lenguaje natural escrita
from nltk.tokenize import word_tokenize #Para procesar los espacios en palabras
from nltk.corpus import stopwords       #Palabras vacías o palabras comunes
import numpy as np                      #Manejos matrices y arreglos multidimensionales
import pandas as pd                     #Manejo, análisis y procesamiento de datos
from nltk.stem import SnowballStemmer   #Stemming algoritmo/método para reducir una palabra a su raíz
from nltk.stem import PorterStemmer
import hashlib
from pyparsing import Word, alphas, oneOf, infixNotation, opAssoc, Literal, QuotedString, ParserElement
from PyQt5.QtWidgets import QApplication, QMainWindow, QTextBrowser, QWidget, QVBoxLayout, QAction, QFileDialog, QLabel, QSplitter, QLineEdit, QListWidget
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QMutex, QWaitCondition, QMutexLocker, QCoreApplication, QTimer
import threading
import time
from Interfaz import InterfazRI

class SistemaRI:
    def __init__(self):
        self.consulta = None
        self.close = False

        #IDIOMA DE STEMMING
        self.spste = SnowballStemmer('spanish')

        #Creamos la carpeta del diccionario
        if not os.path.exists('diccionario'):
            os.makedirs('diccionario')

        #Creamos la carpeta del consultas
        if not os.path.exists('consultas'):
            os.makedirs('consultas')

        self.numero_documentos = 0

        # Directorio que contiene los archivos de texto
        self.directorio = "archivos"
        
        self.nombres_docs = []

        # Definir la gramática para los operadores y operandos
        self.operand = QuotedString("'") | Word(alphas + "0123456789")
        self.not_operator = Literal("!") | Literal("¬")
        self.and_operator = oneOf("&& & ∧")
        self.or_operator = oneOf("|| | ∨")

        self.grammar_elements = ["!", "¬", "&&", "&", "∧", "||", "|", "∨","[", "]"]
        
        # Definir la precedencia de los operadores
        self.precedence = [
            (self.not_operator, 1, opAssoc.RIGHT),
            (self.and_operator, 2, opAssoc.LEFT),
            (self.or_operator, 2, opAssoc.LEFT),
        ]

        # Definir la expresión lógica
        self.expression = infixNotation(self.operand, self.precedence)
    
        self.matriz_binaria = []

        # Definir una lista para las expresiones de la query (palabras)
        self.query_stem_elements = []

        # Definir una lista para los arrays binarios correspondientes a los elementos en la consulta
        self.binary_array_list = []

        # Definir un arreglo para los valores de cada palabra para cada documento
        self.hash_table = {}

        # Definir una lista para cada elemento al momento de realizar la consulta y se tenga que pasar a la notación Post-Fija
        self.postfijo = []

        self.impresion_postfijo = []

        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.consulta_recibida = None

        # Inicializa la interfaz gráfica en un hilo separado
        self.app_thread = threading.Thread(target = self.init_gui_thread)
        self.app_thread.start()

    def init_gui_thread(self):
        # Inicializa la aplicación gráfica en un hilo separado
        self.app = QApplication(sys.argv)
        self.interfaz = InterfazRI(self)

        # Conecta la señal de consulta de la interfaz a una ranura (slot)
        self.interfaz.consulta_signal.connect(self.recibir_consulta)

        # Ejecuta la aplicación gráfica en su propio ciclo de eventos
        self.app.exec_()

    def procesar_texto(self, contenido):
        #Convertimos el texto en minusculas
        contenido = contenido.lower()

        #Limpiamos caracteres especiales por espacios, acentos
        contenido = re.sub(r'[^\w\s]', '', contenido) #Quitamos caracteres especiales
                
        #Quitamos los acentos y limitamos que no modifique la ñ (NFD / descomposición canónica traduce cada carácter a su forma descompuesta)
        contenido = re.sub(r"([^n\u0300-\u036f]|n(?!\u0303(?![\u0300-\u036f])))[\u0300-\u036f]+", r"\1", normalize( "NFD", contenido), 0, re.I) 

        #Quitamos datos numericos
        contenido = re.sub(r'\d+', '', contenido)
                    
        #Separamos el texto por palabras
        contenido = nltk.word_tokenize(contenido)
                
        # Convertimos contenido de type:list a array
        contenido = np.asarray(contenido)

        return contenido

    #Metodo de conversion de la tabla a archivo txt
    def crear_tabla(self, array, nombre):
        df = pd.DataFrame(array, columns=['Palabras'])                      # Agregamos en una columna las palabras
        df = df.groupby(['Palabras']).size().reset_index(name='Frecuencia') #Agrupamos las palabras dada a la frecuencia de veces que aparezcan
        df.sort_values(by=['Frecuencia'],ascending=False, inplace=True)     #Ordenamos las palabras dada a la frecuencia
        df.reset_index(drop=True, inplace=True)                             #Reordenamos los indices por el ranking
        df.to_csv('diccionario/'+nombre+'.txt', index=False,sep="\t")       #Conversion de la tabla a archivo de texto

    #Metodo para crear la matriz binaria
    def crear_matriz_binaria(self, palabras, numero_documentos):
        matriz_binaria = np.zeros((len(palabras), numero_documentos))             #Hacer matriz con la cantidad de 0
        index_palabra = 0                                                         #Contador de indice de la palabra

        for p in palabras:
            index_documento = 0                                  #Contador de indice de documento
            for archivo in os.listdir(self.directorio):          #Lectura de cada documento para ver la aparicion del termino
                ruta = os.path.join(self.directorio, archivo)
                with open(ruta, encoding="utf-8") as doc:
                    contenido = self.procesar_texto(doc.read())
                    doc.close()
                    contenido = [self.spste.stem(word) for word in contenido] #En Español
                    for cnt in contenido:                                       #Comparacion del contendio del doc con el termino
                        if(p == cnt):
                            matriz_binaria[index_palabra][index_documento] = 1  #Si hallamos la igualdad se agrega el 0 y terminamos for
                            break
                index_documento += 1                                            #Incrementos de cada indice de documento y termino
            index_palabra += 1
        self.matriz_binaria = matriz_binaria

    #Metodo para calcular el valor del termino por hast
    def computar_hash(self, word):
        md5_hash = hashlib.md5()            #Crea una instancia del algoritmo md5
        word_bytes = word.encode('utf-8')   #Seleccionamos que tipos de caracter puede leer
        # Actualiza la instancia con los datos que quieres hashear
        # Los datos deben estar en formato de bytes, por lo que usamos el método encode()
        md5_hash.update(word_bytes)
        # Obtiene el hash en formato hexadecimal
        hash_value = md5_hash.hexdigest()
        return hash_value

    #Metodo de creacion de la tabla hash
    def crear_hash_table(self, words, binary_dict):
        hash_table = {}
        for word in words:                      #Recorremos los terminos y sacarmos su valor hash
            hash_value = self.computar_hash(word)
            if hash_value not in hash_table:    #Almacenamos en la tabla dado a su indice en hex
                hash_table[hash_value] = {      #Stem : termino // binary_array : donde aparece el termino
                    'stem': [word],
                    'binary_array': binary_dict.get(word, [])
                }
            else:
                hash_table[hash_value]['words'].append(word)
        self.hash_table = hash_table

    #Metodo para aplicar stopwords y steeming a una cadena
    def token_stopw(self, string):
        # Tokenización
        tokens = word_tokenize(string)

        # Definir una lista de stop words en español
        stop_words = set(stopwords.words('spanish'))

        # Filtrar stop words
        filtered_tokens = [word for word in tokens if word.lower() not in stop_words]

        # Inicializar el stemmer (Porter stemmer)
        stemmer = self.spste

        # Realizar stemming en cada token
        stemmed_tokens = [stemmer.stem(token) for token in filtered_tokens]

        # Unir los tokens stemmeados en una cadena de texto
        texto_procesado = ' '.join(stemmed_tokens)

        return texto_procesado

    #Funcion para procesar la consulta booleana a una lista de elementos
    def procesar_bool_exp(self, query_str):
        bool_exp_list = []

        exp = ""
        in_comilla = False  # Variable para rastrear si estamos dentro de comillas

        for caracter in query_str:
            if in_comilla:  # Si estamos dentro de comillas, agregamos el carácter a exp
                if caracter != "'":
                    exp += caracter
                else:  # Si encontramos otra comilla simple, salimos de las comillas
                    process_exp = self.token_stopw(exp)  #Procesamos cadena de texto
                    bool_exp_list.append(process_exp)   #Almacenamos en el array
                    self.query_stem_elements.append(process_exp)
                    exp = ''                            #Limpiamos variables para reiniciar la busqueda de comillas
                    in_comilla = False
            elif caracter != ' ' and caracter != ',':
                if caracter != "'":
                    bool_exp_list.append(caracter)
                else:
                    in_comilla = True  # Entramos en comillas, comenzamos a construir exp
        return bool_exp_list

    #Se realiza el procesamiento de la notacion postfijo
    def procesar_postfijo(self, bool_exp_list):
        stack_temp = []
        postfijo = []
        i = 0
        # Se recorren los elementos en la lista de expresiones booleanas de la query
        for exp in bool_exp_list:
            i+=1
            # Si el elemento es un operador o parentesis
            if exp in self.grammar_elements:
                # Si el elemento no es un corchete de cierre se agrega al stack temporal
                if exp != "]":
                    stack_temp.append(exp)
                # Si es un corchete que cierra se obtiene el operando y se elimina 
                else:
                    # Se obtiene el elemento del tope del stack
                    elem = stack_temp[-1]
                    print(f"Top element in stack_temp: {elem}")
                    # Mientras no se encuentre el parentesis que cierra se ingresaran los operadores al stack postfijo
                    while elem != "[":
                        operand = stack_temp.pop()
                        postfijo.append(operand)
                        elem = stack_temp[-1]
                        print(f"Element introduced to postfix: {operand}")
                        print(f"Top element in stack_temp: {elem}")
                    # Se elimina el parentesis que abre
                    print("Stack limpiado")
                    stack_temp.pop()
            # Si el elemento es una cadena se pasa a postfijo
            elif exp in self.query_stem_elements:
                postfijo.append(exp)
            # Si aun queda un operador en el stack al terminar se pasa a postfijo
            if i == len(bool_exp_list) and len(stack_temp) > 0:
                        operand = stack_temp.pop()
                        postfijo.append(operand)
            self.interfaz.update_output(f"\nProcesamiento {i}")
            self.impresion_postfijo.append(f"\nProcesamiento {i}")
            self.interfaz.update_output(f"Stack Temp: {stack_temp}")
            self.impresion_postfijo.append(f"Stack Temp: {stack_temp}")
            self.interfaz.update_output(f"Expresion Postfijo: {postfijo}\n")
            self.impresion_postfijo.append(f"Expresion Postfijo: {postfijo}\n")
        self.postfijo = postfijo

    #Realiza la funcion 'or' a dos arrays binarios
    def or_function(self):
        self.interfaz.update_output("\nOperador || (or) seleccionado")
        self.impresion_postfijo.append("\nOperador || (or) seleccionado")
        # Pop las dos últimas listas de binary_array_list
        binary_array1 = self.binary_array_list.pop()
        binary_array2 = self.binary_array_list.pop()
        
        docs_array1 = self.obtener_docs_list(binary_array1)
        docs_array2 = self.obtener_docs_list(binary_array2)
        
        self.interfaz.update_output(f"\n\t{docs_array2} ∨ {docs_array1}")
        self.impresion_postfijo.append(f"\n\t{docs_array2} ∨ {docs_array1}")
        
        num_documentos = len(binary_array1)  # Ambas listas deben tener la misma longitud
        # Crea un nuevo array para almacenar los resultados, inicializado con 0
        resultado = [0] * num_documentos

        # Utiliza un bucle para comparar los elementos en el mismo índice de las dos listas
        for i in range(num_documentos):
            if binary_array1[i] == 1 or binary_array2[i] == 1:
                resultado[i] = 1  # Si un elemento es 1 en cualquiera de las dos listas, establece el resultado en 1

        return resultado

    #Realiza la funcion 'and' a dos arrays binarios
    def and_function(self):
        self.interfaz.update_output("\nOperador && (and) seleccionado")
        self.impresion_postfijo.append("\nOperador && (and) seleccionado")
        # Pop las dos últimas listas de binary_array_list
        binary_array1 = self.binary_array_list.pop()
        binary_array2 = self.binary_array_list.pop()
        
        docs_array1 = self.obtener_docs_list(binary_array1)
        docs_array2 = self.obtener_docs_list(binary_array2)
        
        self.interfaz.update_output(f"\n\t{docs_array2} ∧ {docs_array1}")
        self.impresion_postfijo.append(f"\n\t{docs_array2} ∧ {docs_array1}")
        
        num_documentos = len(binary_array1)  # Ambas listas deben tener la misma longitud
        # Crea un nuevo array para almacenar los resultados, inicializado con 0
        resultado = [0] * num_documentos

        # Utiliza un bucle para comparar los elementos en el mismo índice de las dos listas
        for i in range(num_documentos):
            if binary_array1[i] == 1 and binary_array2[i] == 1:
                resultado[i] = 1  # Si un elemento es 1 en cualquiera de las dos listas, establece el resultado en 1

        return resultado

    #Realiza la funcion 'not' a un array binario
    def not_function(self):
        self.interfaz.update_output("\nOperador ! (not) seleccionado")
        self.impresion_postfijo.append("\nOperador ! (not) seleccionado")
        
        binary_array = self.binary_array_list.pop()
        docs_array = self.obtener_docs_list(binary_array)
        self.interfaz.update_output(f"\n\t¬{docs_array}")
        self.impresion_postfijo.append(f"\n\t¬{docs_array}")
        self.impresion_postfijo.append
        resultado = [1 if doc == 0 else 0 for doc in binary_array]
        return resultado

    #Recibe una consulta desde la interfaz
    def recibir_consulta(self, consulta):
        self.consulta = consulta

        # Almacena la consulta en una variable
        with QMutexLocker(self.mutex):
            self.consulta_recibida = consulta
            self.condition.wakeAll()

    #Espera hasta que la consulta se alla realizado desde la interfaz
    def esperar_consulta(self):
        # Bloquea hasta que se reciba una consulta
        with QMutexLocker(self.mutex):
            while self.consulta_recibida is None:
                self.condition.wait(self.mutex)
            return self.consulta_recibida

    #Metodo de identificacion de operador
    def process_query(self, operator):
        switch = {
            "||": self.or_function,
            "|": self.or_function,
            "∨": self.or_function,
            "&&": self.and_function,
            "&": self.and_function,
            "∧": self.and_function,
            "!": self.not_function,
            "¬": self.not_function
        }
        # Llama a la función correspondiente según el operador
        array_docs = switch.get(operator, lambda: print("Operador no válido"))()
        return array_docs

    def hash_query(self, hash):
        binary_array = None
        # Acceder al diccionario correspondiente al valor_hash
        dict = self.hash_table.get(hash, {})
        # Acceder al array binary_dict dentro del diccionario
        binary_array = dict.get('binary_array', [])

        # Verificar si binary_array está vacío
        if len(binary_array) == 0:
            # Si está vacío, crear un array de ceros, indicando que no existe
            binary_array = [0] * self.numero_documentos

        return binary_array

    def ejecutar_query(self, postfijo):
        self.interfaz.update_output("\nProcesamiento de la consulta:")
        self.impresion_postfijo.append("\nProcesamiento de la consulta:")

        for elem in postfijo:
            # Se verifica si el elemento es una de las palabras a buscar en los documentos
            if elem in self.query_stem_elements:
                # Se calcula el hash de la palabra
                hash = self.computar_hash(elem)
                # Se obtiene su array binario correspondiente en la tabla hash
                array_bin = self.hash_query(hash)
                docs_list = self.obtener_docs_list(array_bin)
                # Se crea una lista de los arrays binarios que se operaran correspondientemente a los operadores logicos
                self.binary_array_list.append(array_bin)
                self.interfaz.update_output(f"\n'{elem}': {docs_list}")
                self.impresion_postfijo.append(f"\n'{elem}': {docs_list}")
            # Si el elemento postfijo es un operador se realiza la operacion con los arrays binarios
            elif elem in self.grammar_elements:
                if len(self.binary_array_list) > 0:
                    # Se obtiene el array correspondiente despues de aplicar la operacion logica
                    array_docs = self.process_query(elem)
                    docs_list = self.obtener_docs_list(array_docs)
                    # Se vacía y se agrega la lista de arrays que usamos para operar en la funcion postfijo
                    self.binary_array_list.append(array_docs)
                    self.interfaz.update_output(f"\n\t{docs_list}")
                    self.impresion_postfijo.append(f"\n\t{docs_list}")
        return self.binary_array_list[0]

    #Metodo donde revisa donde pertenece el documento
    def obtener_docs(self, array_docs,nombre):
        self.interfaz.update_output("\nDocumentos que satisfacen la consulta:\n")
        self.impresion_postfijo.append("\nDocumentos que satisfacen la consulta:\n")
        for i in range(len(array_docs)):
            if array_docs[i] == 1:
                self.interfaz.update_output(f"\t> Documento {i+1} : {nombre[i]}")
                self.impresion_postfijo.append(f"\t> Documento {i+1} : {nombre[i]}")     

    def obtener_docs_list(self, array_docs):
        nombres_docs = []
        for i in range(len(array_docs)):
            if array_docs[i] == 1:
                nombres_docs.append(self.nombres_docs[i])
        return nombres_docs

    #Limpia las variables necesarias para realizar una nueva consulta
    def clear(self):
        self.binary_array_list.clear()
        self.consulta =  ""
        self.postfijo.clear()
        self.query_stem_elements.clear()
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.consulta_recibida = None
        self.impresion_postfijo.clear()

    def terminar_programa(self):
        self.close = True
        self.consulta_recibida = ""
        self.condition.wakeAll()
        print("Programa terminado.")
        sys.exit(0)                
        

##PRINCIPIO DEL PROGRAMA##

def main():
    sistema_ri = SistemaRI()  # Crea una instancia de SistemaRI después de QApplication

    try:
        numero_documentos = 0

        #Array donde almacenaremos las palabras
        diccionario = []
        
        #Nombre de los documentos
        id_doc = []
        nom_doc = []
        
        #Empezamos en revisar el contenido de los archivos de la carpeta
        for archivo in os.listdir(sistema_ri.directorio):
            ruta = os.path.join(sistema_ri.directorio, archivo)
            
            #Almacenamos el nombre del documento
            id_doc.append('D'+str(numero_documentos+1))
            nom_doc.append(archivo)
            sistema_ri.nombres_docs.append(archivo)
            
            with open(ruta, encoding="utf-8") as doc:
                contenido = sistema_ri.procesar_texto(doc.read())
                doc.close()
                
                #Concatenamos las palabras en el diccionario            
                diccionario = np.concatenate((diccionario, contenido))
                numero_documentos += 1
        
        sistema_ri.numero_documentos = numero_documentos 
                
        #Revisamos la frecuencia de cada palabra
        sistema_ri.crear_tabla(diccionario,'Frecuencia')
        
        #Eliminaremos las stopwords y revisamos la longitud de la palabra si es mayor de 2
        diccionario = [word for word in diccionario if word not in stopwords.words("english") and word not in stopwords.words("spanish") and len(word)>2]
        sistema_ri.crear_tabla(diccionario,'Stopwords')
        
        #Reduccion de Steeming
        diccionario = [sistema_ri.spste.stem(word) for word in diccionario] #En Español
        sistema_ri.crear_tabla(diccionario,'Steeming')
        
        #Manejo de la tabla binaria para conversion a txt
        df = pd.DataFrame(diccionario, columns=['Palabras'])                      #Agregamos en una columna las palabras
        df = df.groupby(['Palabras']).size().reset_index(name='Frecuencia')       #Agrupamos las palabras dada a la frecuencia de veces que aparezcan
        df.sort_values(by=['Frecuencia'],ascending=False, inplace=True)           #Ordenamos las palabras dada a la frecuencia
        df.reset_index(drop=True, inplace=True)                                   #Reordenamos los indices por el ranking
        
        palabras = df['Palabras'].to_numpy()                                      #Conversion de Dataframe a Array
        
        sistema_ri.crear_matriz_binaria(palabras, numero_documentos)
        
        #Conversion de los array a dataframe para visualizar en tabla
        df = pd.DataFrame(sistema_ri.matriz_binaria, columns=id_doc)
        df = df.astype(int)
        df.insert(0, "Termino", palabras)
        df.to_csv('diccionario/Matriz_BIN.txt', index=False,sep="\t")       #Conversion de la tabla a archivo de texto
        
        
        #Crear un diccionario para almacenar la información anterior obtenida
        diccionario_binario = {}

        #Obtener un diccionario [palabra]-vector en base a la matríz binaria
        for index, palabra in enumerate(palabras):
            diccionario_binario[palabra] = sistema_ri.matriz_binaria[index, :]

        #Ordenamiento del diccionario binario con procedimiento hash
        sistema_ri.crear_hash_table(palabras, diccionario_binario)

        for i in range(len(nom_doc)):
            sistema_ri.interfaz.update_output(f"> Documento {i+1} : {nom_doc[i]}")
        
        sistema_ri.interfaz.update_output(f"\nGrammar elements {sistema_ri.grammar_elements}")
        
        i=1
        while True:

            print(f"Consulta {i}")
            #Pedir la consulta booleana al usuario
            print("Esperando consulta...")
            consulta = sistema_ri.esperar_consulta()  # Espera a que se reciba una consulta
            
            if sistema_ri.close:
                break
            
            print(f"Consulta recibida: {consulta}")

            #Se analizar una cadena de texto y convertirla en una expresión o consulta que puede ser procesada por un programa.
            format_expresion = sistema_ri.expression.parseString(consulta)
            
            # Convierte ParseResults en una lista y luego en una cadena
            result_list = [str(item) for item in format_expresion]
            query_str = ''.join(result_list)
                
            #Procesamos el proceso de booleana
            bool_exp_list = sistema_ri.procesar_bool_exp(query_str)

            #Quitar el corchete extra al inicio y al final
            bool_exp_list = bool_exp_list[1:-1]
            sistema_ri.interfaz.update_output(f"\n\nQuery Expresion List: {bool_exp_list}")
            sistema_ri.impresion_postfijo.append(f"Query Expresion List: {bool_exp_list}")

                #Se establace los terminos sin expresiones
            sistema_ri.query_stem_elements = [elemento for elemento in sistema_ri.query_stem_elements if elemento not in sistema_ri.grammar_elements]
                
            sistema_ri.interfaz.update_output(f"Stem Elements{sistema_ri.query_stem_elements}")
            sistema_ri.impresion_postfijo.append(f"Stem Elements{sistema_ri.query_stem_elements}")
                #Procesamiento de infija a postfija
            sistema_ri.procesar_postfijo(bool_exp_list)
            sistema_ri.interfaz.update_output(f"\nExpresion Postfijo Final: {sistema_ri.postfijo}\n")
            sistema_ri.impresion_postfijo.append(f"Expresion Postfijo Final: {sistema_ri.postfijo}")
                
            #Ejecucion de la consulta booleana
            array_docs = sistema_ri.ejecutar_query(sistema_ri.postfijo)

            #Resultado de documentos aparece la consulta
            sistema_ri.obtener_docs(array_docs, nom_doc)
            
            sistema_ri.interfaz.update_output("\n------------------------------------------------------------------------------------------------------------------")
            
            with open(f"consultas/Consulta_{i}.txt", "a", encoding = "utf-8") as f:
                for item in sistema_ri.impresion_postfijo:
                    f.write("%s\n" % item)
                    
            sistema_ri.clear()
            i+=1
        pass
        
    except Exception as e: #Si hay un error en un archivo de identificara
        print(f"\n <!> : {str(e)}")
    sys.exit(sistema_ri.app.exec_())

if __name__ == '__main__':
    main()