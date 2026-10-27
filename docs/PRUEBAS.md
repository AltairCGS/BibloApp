# Pruebas automatizadas

BibloApp incluye **209 pruebas** que verifican las funciones del sistema y,
sobre todo, sus errores esperados. Corren en pocos segundos y no necesitan la
interfaz gráfica.

## Cómo ejecutarlas

Doble clic en `run_pruebas.bat`, o desde la consola:

```bat
.venv\Scripts\python.exe -m pytest
```

Resultado esperado:

```
209 passed in ~8s
```

Si algo falla, pytest muestra el archivo, la línea y los valores que compara.

## Qué es una prueba, en concreto

Cada prueba llama a una función con datos conocidos y compara el resultado
con el esperado:

```python
def test_no_se_puede_repetir_un_codigo_de_inventario(
    como_admin: None, libro_demo: Callable[[str], dict]
) -> None:
    libro = libro_demo("Ficciones")

    ok, mensaje, ejemplar_id = catalogo.agregar_ejemplar(
        libro["id"], {"codigo_inventario": "ej-00001"}
    )

    assert not ok
    assert "Ya existe un ejemplar" in mensaje
    assert ejemplar_id is None
```

No solo confirman lo que sale bien: fijan los **errores que deben seguir
ocurriendo**. Si alguien modifica el código para que acepte un código
repetido, esta prueba falla y avisa antes de que el error llegue a la
biblioteca.

## Base de datos de prueba

Cada corrida crea una base SQLite temporal en la carpeta de temporales de
Windows y trabaja ahí. `data/biblioteca.db` no se abre en ningún momento:
antes de empezar, la suite comprueba la ruta y se detiene si no es temporal.
Al terminar, la borra.

El catálogo de demostración se reconstruye antes de cada prueba, así que
ninguna depende del orden en que se ejecuten las demás.

## Qué cubre

| Archivo | Pruebas | Qué verifica |
|---|---:|---|
| `test_seguridad.py` | 11 | Formato del hash, clave correcta e incorrecta, salt distinto por cuenta, hash corrupto |
| `test_auth.py` | 19 | Login, cuenta desactivada, mensaje que no revela si el usuario existe, auditoría, matriz de permisos |
| `test_permisos_servicios.py` | 8 | Que el auxiliar no pueda escribir aunque llame al servicio directamente |
| `test_catalogo.py` | 23 | Búsqueda sin tildes ni mayúsculas, ISBN, categorías, disponibilidad, altas, edición y reglas de borrado |
| `test_socios.py` | 59 | Validación de fichas, documento único, búsqueda, filtros, historial, situación (activo, gracia, bloqueado, suspendido, baja) y reglas de préstamo |
| `test_prestamos.py` | 33 | Salidas con validación de disponibilidad, situación y límite; devoluciones, renovaciones, vencidos, filtros y permisos |
| `test_vencidos.py` | 12 | Listado de abiertos fuera de plazo, orden por atraso, búsqueda, gracia, resumen, CSV con BOM y auditoría, devolución y pérdida desde Vencidos |
| `test_multas.py` | 19 | Pérdida de ejemplares, cierre del préstamo, multa generada, bloqueo del socio, pago, anulación, filtros y permisos |
| `test_recuperacion.py` | 14 | Recuperación de un perdido, estado del ejemplar, anulación de la multa pendiente, advertencia en el socio, filtros, contadores y permisos |
| `test_base_datos.py` | 5 | Commit, rollback ante error, claves foráneas activas, respaldos |
| `test_importar.py` | 6 | Importación, autores y palabras clave, idempotencia, reemplazo bloqueado por préstamos |

### Errores esperados que quedan fijados

- Libro sin título.
- Código de inventario repetido.
- Eliminar un libro con préstamos registrados.
- Eliminar un ejemplar prestado o con historial.
- Cambiar a mano el estado de un ejemplar prestado.
- Socio sin nombre, documento fuera de rango o email inválido.
- Documento de socio repetido.
- Eliminar un socio con préstamos registrados.
- Socio suspendido, dado de baja o bloqueado por atraso: no puede retirar material.
- Ejemplar prestado, en reparación o dado de baja: no se puede prestar.
- Socio en el límite de ejemplares: no puede retirar otra copia.
- Devolver dos veces el mismo préstamo.
- Marcar como perdido un préstamo ya cerrado o que ya figura como perdido.
- Recuperar un préstamo que no figura como perdido, recuperarlo dos veces o
  hacerlo sin el permiso de socios.
- Retirar material con una multa pendiente.
- Cobrar una multa anulada o anular una multa ya pagada.
- Renovar un préstamo devuelto, vencido, sin renovaciones disponibles o con
  el socio suspendido o con otros vencidos fuera de gracia.
- Exportar recordatorios sin préstamos vencidos o sin permiso.
- Cuenta desactivada.
- Credenciales vacías.
- Hash de contraseña corrupto.
- Importar un catálogo cuando ya hay préstamos.
- Escritura sin permiso o sin sesión iniciada.

## Qué no cubre

Siendo honesto con el alcance:

- **Interfaz gráfica.** No hay pruebas automáticas de ventanas ni widgets;
  esas se verifican con capturas y uso manual.
- **Rendimiento** con miles de registros.
- **Concurrencia.** El diseño es de una sola PC y un solo usuario por vez.
- **Cifrado de la base** y política de contraseñas: todavía no existen.
- **Migraciones de esquema.** `create_all` no altera tablas existentes.

## Las pruebas como documentación

Un nombre de prueba bien escrito describe el comportamiento esperado sin
necesidad de leer la implementación:

```
test_no_se_puede_eliminar_un_libro_con_prestamos
test_usuario_inexistente_y_clave_erronea_dan_el_mismo_mensaje
test_el_formulario_no_puede_cambiar_el_estado_de_un_ejemplar_prestado
```

Eso es lo que algunos proyectos llaman *documentación viva*: no describe lo
que el sistema debería hacer según un documento aparte, sino lo que **hace
hoy**, y falla en el momento en que deja de ser cierto.

## Comprobación de que la suite detecta regresiones

Para no entregar pruebas decorativas, se quitó a propósito el guardia de
permisos de `crear_libro`: la prueba correspondiente falló
(`test_el_auxiliar_no_puede_crear_un_libro`), y el archivo se restauró
verificando que su SHA-256 fuera idéntico al original.

## Agregar una prueba nueva

1. Crear o abrir el archivo `tests/test_*.py` del área correspondiente.
2. Usar los fixtures de `tests/conftest.py`:
   - `como_admin`, `como_bibliotecario`, `como_auxiliar`: sesión iniciada.
   - `libro_demo("Título")`: busca un libro de la semilla.
   - `crear_socio(...)`: crea un socio suelto.
   - `prestar(ejemplar_id)`: préstamo de un ejemplar (crea su propio socio).
   - `prestar_a(socio_id, ejemplar_id, dias_desde=...)`: préstamo de un socio
     concreto; `dias_desde` simula atrasos sin esperar días reales.
3. Nombrar la función con `test_` y una frase que describa la regla.
4. Ejecutar `run_pruebas.bat`.
