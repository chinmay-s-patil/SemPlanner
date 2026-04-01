"""planner/utils/scroll_utils.py — Unified mouse-wheel scroll binding."""


def bind_scroll(canvas, h_canvas=None):
    """
    Attach mouse-wheel scroll events to *canvas* **and all descendants**.

    Vertical:   Button-4/5 (Linux), MouseWheel (Win/Mac)
    Horizontal: Shift+Button-4/5, Shift+MouseWheel
                (uses *h_canvas* if provided, else *canvas*)

    Events are bound to the canvas itself *and* recursively to every
    child widget so that scrolling works even when the pointer sits on
    top of labels, frames, buttons, etc. inside the scrollable area.
    """
    def _y(n):
        canvas.yview_scroll(n, "units")

    def _x(n):
        (h_canvas or canvas).xview_scroll(n, "units")

    def _bind_widget(w):
        w.bind("<Button-4>",         lambda e: _y(-3))
        w.bind("<Button-5>",         lambda e: _y(3))
        w.bind("<Shift-Button-4>",   lambda e: _x(-3))
        w.bind("<Shift-Button-5>",   lambda e: _x(3))
        w.bind("<MouseWheel>",       lambda e: _y(int(-e.delta / 120)))
        w.bind("<Shift-MouseWheel>", lambda e: _x(int(-e.delta / 120)))

    _bind_widget(canvas)

    # Also bind the inner frame (window) and all descendants
    def _bind_recursive(parent):
        for child in parent.winfo_children():
            _bind_widget(child)
            _bind_recursive(child)

    # Bind existing children now
    _bind_recursive(canvas)

    # Make sure we don't bind on <Configure> since that causes massive
    # slowdowns/infinite loops when scrolling or resizing. The app must
    # manually call rebind_scroll_children() after redrawing content.


def rebind_scroll_children(canvas, content_frame, h_canvas=None):
    """
    Call after dynamically rebuilding the content inside *canvas*.

    Re-applies mouse-wheel bindings to every widget inside
    *content_frame* so scrolling works on new labels/entries/etc.
    """
    def _y(n):
        canvas.yview_scroll(n, "units")

    def _x(n):
        (h_canvas or canvas).xview_scroll(n, "units")

    def _bind_widget(w):
        w.bind("<Button-4>",         lambda e: _y(-3))
        w.bind("<Button-5>",         lambda e: _y(3))
        w.bind("<Shift-Button-4>",   lambda e: _x(-3))
        w.bind("<Shift-Button-5>",   lambda e: _x(3))
        w.bind("<MouseWheel>",       lambda e: _y(int(-e.delta / 120)))
        w.bind("<Shift-MouseWheel>", lambda e: _x(int(-e.delta / 120)))

    def _bind_recursive(parent):
        for child in parent.winfo_children():
            _bind_widget(child)
            _bind_recursive(child)

    _bind_widget(content_frame)
    _bind_recursive(content_frame)
