# Demo de Vencidos

Esta carpeta sirve para probar la pantalla **Vencidos** y exportar un CSV sin
tocar la base real `data/biblioteca.db`.

## Cómo abrirla

Doble clic en **`abrir_vencidos_demo.bat`**.

- Usuario: `admin`
- Contraseña: `admin123`

La aplicación se abre apuntando a `demo/vencidos_demo.db`.

## Qué datos trae

- El catálogo de ejemplo completo: 80 libros y 103 ejemplares.
- **8 socios de ficción**, con correos de `example.com` y teléfonos `555-01xx`.
- **8 préstamos vencidos**, con atrasos de 45, 30, 23, 12, 7, 5, 3 y 1 días.
- 6 quedan **fuera del plazo de gracia** (3 días) y 2 dentro.
- Un socio **sin teléfono ni correo**, para ver el caso «Sin contacto».
- Un préstamo devuelto y otro activo al día que **no** aparecen en Vencidos.

## Cómo exportar el CSV

1. Entrar con `admin` / `admin123`.
2. Ir a **Vencidos**.
3. Opcional: probar el check **Solo fuera de gracia**.
4. Pulsar **Exportar CSV** y elegir dónde guardar.
5. Abrir el archivo con Excel: las tildes y las fechas se ven correctamente.

## Regenerar la demo

Si querés volver a los datos originales (por ejemplo, después de devolver o
marcar perdido algún préstamo), cerrá la app y ejecutá:

```bat
.venv\Scripts\python.exe demo\crear_demo_vencidos.py
```

Eso reemplaza únicamente `demo/vencidos_demo.db`. La base real nunca se abre.
