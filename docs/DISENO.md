# Guía de diseño e interfaz

BibloApp no usa archivos `.ui` ni Qt Designer: **toda la interfaz está escrita
en Python** con PySide6. Eso significa que Qt Designer no puede abrir estas
ventanas, pero sí se pueden ver y modificar de otra forma muy directa.

## Cómo abrir las ventanas

1. Doble clic en `run.bat` (o `\.venv\Scripts\python.exe -m app.main`).
2. Iniciar sesión con una de las cuentas de prueba:

   | Usuario | Contraseña | Rol |
   |---|---|---|
   | `admin` | `admin123` | Administrador |
   | `bibliotecario` | `biblio123` | Bibliotecario |
   | `auxiliar` | `aux123` | Auxiliar |

3. En la barra lateral entrar a **Catálogo**, **Socios**, etc.
4. Para ver los formularios:
   - Catálogo → seleccionar un libro → **Editar libro** o **Agregar ejemplar**.
   - Socios → seleccionar un socio → **Editar socio**, o **+ Nuevo socio**.
   - Préstamos → **+ Nuevo préstamo**; con una fila elegida,
     **Registrar devolución**, **Renovar** o **Marcar perdido**. Si la fila
     figura como perdida, se habilita **Marcar recuperado**.
   - Vencidos → **Exportar CSV**; con una fila elegida,
     **Registrar devolución** o **Marcar perdido**. El check
     **Solo fuera de gracia** oculta los atrasos tolerados.
   - Socios → ficha del socio → **Registrar pago** o **Anular multa**, y el
     aviso naranja con las advertencias por recuperaciones.

Los roles cambian el menú: el auxiliar no ve Catálogo ni Socios, solo
Préstamos y Vencidos. Eso permite comprobar cómo queda la app para cada uno.

## Dónde se cambia cada cosa

| Quiero cambiar… | Archivo |
|---|---|
| Colores de toda la app | `app/ui/theme.py` (paleta, primeras líneas) |
| Tipografía | `app/ui/theme.py` (`FUENTE`) y `app/main.py` (`QFont`) |
| Botones, tablas, avisos, badges | `app/ui/theme.py` (hoja QSS) |
| Menú lateral y módulos | `app/ui/views/main_window.py` (`MODULOS`) |
| Pantalla de socios | `app/ui/views/socios.py` |
| Pantalla de préstamos | `app/ui/views/prestamos.py` |
| Pantalla de vencidos | `app/ui/views/vencidos.py` |
| Pantalla de catálogo | `app/ui/views/catalogo.py` |
| Panel principal | `app/ui/views/dashboard.py` |
| Login | `app/ui/views/login.py` |
| Formularios (libro, ejemplar, socio, préstamo, devolución, pérdida, recuperación) | `app/ui/widgets/dialogos.py` |
| Tarjetas y etiquetas de estado | `app/ui/widgets/cards.py` |

## Ejemplo: cambiar el color de acento

En `app/ui/theme.py`:

```python
ACENTO = "#23648A"
ACENTO_HOVER = "#1B5070"
ACENTO_SUAVE = "#E8F1F7"
```

Cambiar los tres por otra familia de azul (o verde, etc.), cerrar la app y
volver a abrirla. El color se usa en botones principales, selección de tablas,
enlaces y badges.

## Ejemplo: cambiar el ancho de la ficha de socio

En `app/ui/views/socios.py`, dentro de `_construir`:

```python
divisor.setSizes([700, 420])
```

El primer número es el listado y el segundo la ficha. También se puede mover
con el mouse al ejecutar la app: el divisor es arrastrable.

## Ejemplo: cambiar el orden del menú

En `app/ui/views/main_window.py`, la lista `MODULOS`:

```python
("socios", "Socios", "socios", "Socios", "Fichas, historial y estado"),
# clave, etiqueta, permiso, título de barra, subtítulo
```

Mover la tupla de lugar cambia el orden en la barra lateral.

## Cómo probar un cambio

1. Cerrar la app si está abierta.
2. Editar el archivo.
3. Guardar y ejecutar de nuevo `run.bat`.
4. Revisar a **1280×800** (tamaño por defecto) y, si se puede, a **1920×1080**.
5. Para los formularios, abrirlos desde la pantalla correspondiente.

No hay recarga en caliente: los cambios se ven al reiniciar. Si algo no
compila, la consola muestra el archivo y la línea.

## Cuidados

- **No editar `data/biblioteca.db`** a mano: la app la abre y la usa.
- La interfaz **no está cubierta por pruebas automáticas**; los cambios de
  diseño se verifican abriendo la app.
- El proyecto usa Git. Antes de un cambio grande conviene crear una rama y
  revisar los cambios con `git diff` antes de confirmarlos.
- Qt Designer sirve para crear archivos `.ui`, pero esta app no los usa. Migrar
  a `.ui` sería un cambio de arquitectura, no una simple vista previa.

## Si querés una vista previa más rápida

Se puede agregar un pequeño comando de desarrollo que abra directamente una
pantalla con datos de demostración, sin pasar por el login. No existe todavía;
si te resulta útil, se puede crear sin tocar la app principal.
