/*
 * Copyright 2026 Vendekagon Labs LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/* transit._native: reading and writing transit with transit-format-c,
 * producing and taking the same Python objects as the pure Python reader
 * and writer. Uses only the limited API (Python 3.10+), so one wheel per
 * platform covers every Python version. */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <string.h>

#include "transit.h"
#include "transit_c_version.h"

/* Looked up once at import. */
static PyObject *Keyword, *Symbol, *URI, *TaggedValue, *Link, *Frozendict;
static PyObject *T_true, *T_false;
static PyObject *UUID, *Decimal, *Datetime, *Timedelta, *Epoch, *OneMs, *B2aBase64;
static PyObject *Unsupported;   /* raised to hand a value back to the pure writer */

#define MAX_DEPTH 1000

/* Reading */

static PyObject *text(const char *s, size_t len) {
    return PyUnicode_DecodeUTF8(s, (Py_ssize_t)len, "surrogatepass");
}

static PyObject *call1(PyObject *f, PyObject *arg) {
    PyObject *r;
    if (!arg) return NULL;
    r = PyObject_CallFunctionObjArgs(f, arg, NULL);
    Py_DECREF(arg);
    return r;
}

static PyObject *call_kw(PyObject *f, const char *name, PyObject *arg) {
    PyObject *args, *kwargs, *r = NULL;
    if (!arg) return NULL;
    args = PyTuple_New(0);
    kwargs = PyDict_New();
    if (args && kwargs && PyDict_SetItemString(kwargs, name, arg) == 0) r = PyObject_Call(f, args, kwargs);
    Py_XDECREF(args);
    Py_XDECREF(kwargs);
    Py_DECREF(arg);
    return r;
}

/* Keywords and symbols repeat a lot, and are immutable, so each loads()
 * call makes one object per distinct name. */
/* cache: a dict of (class, name) -> object for one loads() call */
static PyObject *named(PyObject *cache, PyObject *cls, const char *s, size_t len) {
    PyObject *name = text(s, len), *key, *obj;
    if (!name) return NULL;
    key = PyTuple_Pack(2, cls, name);
    if (!key) {
        Py_DECREF(name);
        return NULL;
    }
    obj = PyDict_GetItemWithError(cache, key);
    if (obj) {
        Py_INCREF(obj);
    } else if (!PyErr_Occurred()) {
        obj = PyObject_CallFunctionObjArgs(cls, name, NULL);
        if (obj && PyDict_SetItem(cache, key, obj) < 0) Py_CLEAR(obj);
    }
    Py_DECREF(key);
    Py_DECREF(name);
    return obj;
}

/* frozendict(d) copies d; this makes one around d without copying. */
static PyObject *make_frozendict(PyObject *d) {
    PyObject *fd;
    if (!d) return NULL;
    fd = PyObject_CallMethod((PyObject *)&PyBaseObject_Type, "__new__", "O", Frozendict);
    if (fd && PyObject_SetAttrString(fd, "_dict", d) < 0) Py_CLEAR(fd);
    Py_DECREF(d);
    return fd;
}

static PyObject *to_py(PyObject *cache, const transit_value *v, int depth);

static PyObject *items_tuple(PyObject *cache, const transit_value *v, int depth) {
    size_t i, n = v->u.coll.count;
    PyObject *t = PyTuple_New((Py_ssize_t)n);
    if (!t) return NULL;
    for (i = 0; i < n; i++) {
        PyObject *item = to_py(cache, v->u.coll.items[i], depth + 1);
        if (!item || PyTuple_SetItem(t, (Py_ssize_t)i, item) < 0) {
            Py_DECREF(t);
            return NULL;
        }
    }
    return t;
}

static PyObject *map_dict(PyObject *cache, const transit_value *v, int depth) {
    size_t i;
    PyObject *d = PyDict_New();
    if (!d) return NULL;
    for (i = 0; i < v->u.map.count; i++) {
        PyObject *k = to_py(cache, v->u.map.keys[i], depth + 1), *val;
        if (!k) goto fail;
        val = to_py(cache, v->u.map.values[i], depth + 1);
        if (!val || PyDict_SetItem(d, k, val) < 0) {
            Py_DECREF(k);
            Py_XDECREF(val);
            goto fail;
        }
        Py_DECREF(k);
        Py_DECREF(val);
    }
    return d;
fail:
    Py_DECREF(d);
    return NULL;
}

static PyObject *to_py(PyObject *cache, const transit_value *v, int depth) {
    if (depth > MAX_DEPTH) {
        PyErr_SetString(PyExc_RecursionError, "transit value nested too deeply");
        return NULL;
    }
    switch (v->type) {
    case TRANSIT_NIL:
        Py_INCREF(Py_None);
        return Py_None;
    case TRANSIT_BOOL: {
        PyObject *b = v->u.boolean ? T_true : T_false;
        Py_INCREF(b);
        return b;
    }
    case TRANSIT_INT:
        return PyLong_FromLongLong((long long)v->u.integer);
    case TRANSIT_BIGINT: {
        char *s = (char *)PyMem_Malloc(v->u.str.len + 1);
        PyObject *r;
        if (!s) return PyErr_NoMemory();
        memcpy(s, v->u.str.data, v->u.str.len);
        s[v->u.str.len] = '\0';
        r = PyLong_FromString(s, NULL, 10);
        PyMem_Free(s);
        return r;
    }
    case TRANSIT_FLOAT:
        return PyFloat_FromDouble(v->u.number);
    case TRANSIT_DECIMAL:
        return call1(Decimal, text(v->u.str.data, v->u.str.len));
    case TRANSIT_STRING:
        return text(v->u.str.data, v->u.str.len);
    case TRANSIT_KEYWORD:
        return named(cache, Keyword, v->u.str.data, v->u.str.len);
    case TRANSIT_SYMBOL:
        return named(cache, Symbol, v->u.str.data, v->u.str.len);
    case TRANSIT_URI:
        return call1(URI, text(v->u.str.data, v->u.str.len));
    case TRANSIT_BYTES: {
        /* the pure reader has no "b" decoder: bytes are a tagged value */
        PyObject *raw, *r;
        raw = PyBytes_FromStringAndSize(v->u.str.data, (Py_ssize_t)v->u.str.len);
        if (!raw) return NULL;
        {
            PyObject *args = PyTuple_Pack(1, raw), *kwargs = PyDict_New(), *enc;
            Py_DECREF(raw);
            if (!args || !kwargs || PyDict_SetItemString(kwargs, "newline", Py_False) < 0) {
                Py_XDECREF(args);
                Py_XDECREF(kwargs);
                return NULL;
            }
            enc = PyObject_Call(B2aBase64, args, kwargs);
            Py_DECREF(args);
            Py_DECREF(kwargs);
            if (!enc) return NULL;
            r = PyUnicode_FromEncodedObject(enc, "ascii", "strict");
            Py_DECREF(enc);
            if (!r) return NULL;
            return PyObject_CallFunction(TaggedValue, "sN", "b", r);
        }
    }
    case TRANSIT_TIME: {
        PyObject *delta = PyObject_CallFunction(Timedelta, "iiiL", 0, 0, 0, (long long)v->u.integer), *r;
        if (!delta) return NULL;
        r = PyNumber_Add(Epoch, delta);
        Py_DECREF(delta);
        return r;
    }
    case TRANSIT_UUID:
        return call_kw(UUID, "bytes", PyBytes_FromStringAndSize((const char *)v->u.uuid, 16));
    case TRANSIT_ARRAY:
    case TRANSIT_LIST:
        return items_tuple(cache, v, depth);
    case TRANSIT_SET: {
        PyObject *t = items_tuple(cache, v, depth), *s;
        if (!t) return NULL;
        s = PyFrozenSet_New(t);
        Py_DECREF(t);
        return s;
    }
    case TRANSIT_MAP:
        return make_frozendict(map_dict(cache, v, depth));
    case TRANSIT_TAGGED: {
        const char *tag = v->u.tagged.tag;
        size_t tag_len = v->u.tagged.tag_len;
        if (tag_len == 4 && memcmp(tag, "link", 4) == 0 && v->u.tagged.rep->type == TRANSIT_MAP) {
            PyObject *d = map_dict(cache, v->u.tagged.rep, depth), *args, *r;
            if (!d) return NULL;
            args = PyTuple_New(0);
            r = args ? PyObject_Call(Link, args, d) : NULL;
            Py_XDECREF(args);
            Py_DECREF(d);
            return r;
        }
        {
            PyObject *t = text(tag, tag_len), *rep, *r;
            if (!t) return NULL;
            rep = to_py(cache, v->u.tagged.rep, depth + 1);
            if (!rep) {
                Py_DECREF(t);
                return NULL;
            }
            r = PyObject_CallFunctionObjArgs(TaggedValue, t, rep, NULL);
            Py_DECREF(t);
            Py_DECREF(rep);
            return r;
        }
    }
    }
    PyErr_SetString(PyExc_ValueError, "unknown transit value");
    return NULL;
}

static int get_format(int format, transit_format *out) {
    if (format < 0 || format > 2) {
        PyErr_SetString(PyExc_ValueError, "format must be 0 (json), 1 (json_verbose) or 2 (msgpack)");
        return -1;
    }
    *out = (transit_format)format;
    return 0;
}

static PyObject *native_loads(PyObject *self, PyObject *args) {
    PyObject *data, *r;
    int format_i;
    transit_format format;
    const char *buf;
    Py_ssize_t len;
    transit_doc *doc;
    transit_value *v;
    transit_error err;
    (void)self;
    if (!PyArg_ParseTuple(args, "Oi", &data, &format_i) || get_format(format_i, &format)) return NULL;
    if (PyUnicode_Check(data)) {
        buf = PyUnicode_AsUTF8AndSize(data, &len);
        if (!buf) return NULL;
    } else if (PyBytes_Check(data)) {
        char *b;
        if (PyBytes_AsStringAndSize(data, &b, &len) < 0) return NULL;
        buf = b;
    } else {
        PyErr_SetString(PyExc_TypeError, "expected str or bytes");
        return NULL;
    }
    doc = transit_doc_new();
    if (!doc) return PyErr_NoMemory();
    v = transit_read(doc, buf, (size_t)len, format, &err);
    if (!v) {
        transit_doc_free(doc);
        PyErr_SetString(PyExc_ValueError, err.message);
        return NULL;
    }
    {
        PyObject *cache = PyDict_New();
        r = cache ? to_py(cache, v, 0) : NULL;
        Py_XDECREF(cache);
    }
    transit_doc_free(doc);
    return r;
}

/* Writing */

static transit_value *unsupported(void) {
    if (!PyErr_Occurred()) PyErr_SetNone(Unsupported);
    return NULL;
}

static transit_value *str_value(transit_doc *doc, PyObject *s,
                                transit_value *(*make)(transit_doc *, const char *, size_t)) {
    Py_ssize_t len;
    const char *u;
    if (!s) return NULL;
    u = PyUnicode_Check(s) ? PyUnicode_AsUTF8AndSize(s, &len) : NULL;
    if (!u) {
        /* not a str, or not encodable (lone surrogates): leave it to Python */
        PyErr_Clear();
        return unsupported();
    }
    return make(doc, u, (size_t)len);
}

static transit_value *attr_str(transit_doc *doc, PyObject *o, const char *name,
                               transit_value *(*make)(transit_doc *, const char *, size_t)) {
    PyObject *s = PyObject_GetAttrString(o, name);
    transit_value *v;
    if (!s) return NULL;
    v = str_value(doc, s, make);
    Py_DECREF(s);
    return v;
}

static transit_value *from_py(transit_doc *doc, PyObject *o, int depth);

static transit_value *from_iterable(transit_doc *doc, PyObject *o, transit_value *coll, int depth) {
    PyObject *it = PyObject_GetIter(o), *item;
    if (!it || !coll) return NULL;
    while ((item = PyIter_Next(it))) {
        transit_value *v = from_py(doc, item, depth + 1);
        Py_DECREF(item);
        if (!v || transit_push(doc, coll, v)) {
            Py_DECREF(it);
            return v ? (transit_value *)PyErr_NoMemory() : NULL;
        }
    }
    Py_DECREF(it);
    return PyErr_Occurred() ? NULL : coll;
}

static transit_value *from_dict(transit_doc *doc, PyObject *d, int depth) {
    transit_value *m = transit_map(doc);
    Py_ssize_t pos = 0;
    PyObject *k, *val;
    if (!m) return (transit_value *)PyErr_NoMemory();
    while (PyDict_Next(d, &pos, &k, &val)) {
        transit_value *tk = from_py(doc, k, depth + 1), *tv;
        if (!tk || !(tv = from_py(doc, val, depth + 1))) return NULL;
        if (transit_map_put(doc, m, tk, tv)) return (transit_value *)PyErr_NoMemory();
    }
    return m;
}

static transit_value *from_py(transit_doc *doc, PyObject *o, int depth) {
    PyTypeObject *t = Py_TYPE(o);
    if (depth > MAX_DEPTH) return unsupported();
    if (o == Py_None) return transit_nil(doc);
    if (o == T_true || o == Py_True) return transit_bool(doc, 1);
    if (o == T_false || o == Py_False) return transit_bool(doc, 0);
    if (t == &PyLong_Type) {
        int overflow;
        long long i = PyLong_AsLongLongAndOverflow(o, &overflow);
        if (overflow) {
            PyObject *s = PyObject_Str(o);
            transit_value *v = str_value(doc, s, transit_bigint);
            Py_XDECREF(s);
            return v;
        }
        if (i == -1 && PyErr_Occurred()) return NULL;
        return transit_int(doc, (int64_t)i);
    }
    if (t == &PyFloat_Type) return transit_float(doc, PyFloat_AsDouble(o));
    if (t == &PyUnicode_Type) return str_value(doc, o, transit_string);
    if (t == &PyTuple_Type || t == &PyList_Type) return from_iterable(doc, o, transit_array(doc), depth);
    if (t == &PyDict_Type) return from_dict(doc, o, depth);
    if (t == &PySet_Type || t == &PyFrozenSet_Type) return from_iterable(doc, o, transit_set(doc), depth);
    if ((PyObject *)t == Frozendict) {
        PyObject *d = PyObject_GetAttrString(o, "_dict");
        transit_value *v;
        if (!d) return NULL;
        v = PyDict_Check(d) ? from_dict(doc, d, depth) : unsupported();
        Py_DECREF(d);
        return v;
    }
    if ((PyObject *)t == Keyword) return attr_str(doc, o, "str", transit_keyword);
    if ((PyObject *)t == Symbol) return attr_str(doc, o, "str", transit_symbol);
    if ((PyObject *)t == URI) return attr_str(doc, o, "rep", transit_uri);
    if ((PyObject *)t == UUID) {
        PyObject *b = PyObject_GetAttrString(o, "bytes");
        char *data;
        Py_ssize_t len;
        transit_value *v = NULL;
        if (!b) return NULL;
        if (PyBytes_AsStringAndSize(b, &data, &len) == 0 && len == 16) v = transit_uuid(doc, (const unsigned char *)data);
        Py_DECREF(b);
        return v ? v : unsupported();
    }
    if ((PyObject *)t == Datetime) {
        PyObject *delta = PyNumber_Subtract(o, Epoch), *ms;
        long long i;
        if (!delta) {
            PyErr_Clear();   /* naive datetimes: the pure writer reports it */
            return unsupported();
        }
        ms = PyNumber_FloorDivide(delta, OneMs);
        Py_DECREF(delta);
        if (!ms) return NULL;
        i = PyLong_AsLongLong(ms);
        Py_DECREF(ms);
        if (i == -1 && PyErr_Occurred()) return NULL;
        return transit_time(doc, (int64_t)i);
    }
    if ((PyObject *)t == Decimal) {
        PyObject *s = PyObject_Str(o);
        transit_value *v = str_value(doc, s, transit_decimal);
        Py_XDECREF(s);
        return v;
    }
    if ((PyObject *)t == TaggedValue) {
        PyObject *tag = PyObject_GetAttrString(o, "tag"), *rep;
        Py_ssize_t len;
        const char *tag_s;
        transit_value *tr;
        if (!tag) return NULL;
        tag_s = PyUnicode_Check(tag) ? PyUnicode_AsUTF8AndSize(tag, &len) : NULL;
        if (!tag_s) {
            Py_DECREF(tag);
            PyErr_Clear();
            return unsupported();
        }
        rep = PyObject_GetAttrString(o, "rep");
        tr = rep ? from_py(doc, rep, depth + 1) : NULL;
        Py_XDECREF(rep);
        {
            transit_value *v = tr ? transit_tagged(doc, tag_s, (size_t)len, tr) : NULL;
            Py_DECREF(tag);
            return v;
        }
    }
    if ((PyObject *)t == Link) {
        PyObject *m = PyObject_GetAttrString(o, "as_map");
        transit_value *rep, *v;
        if (!m) return NULL;
        rep = PyDict_Check(m) ? from_dict(doc, m, depth) : unsupported();
        Py_DECREF(m);
        v = rep ? transit_tagged(doc, "link", 4, rep) : NULL;
        return v;
    }
    return unsupported();
}

static PyObject *native_dumps(PyObject *self, PyObject *args) {
    PyObject *o, *r = NULL;
    int format_i;
    transit_format format;
    transit_doc *doc;
    transit_value *v;
    transit_buffer out = {0};
    transit_error err;
    (void)self;
    if (!PyArg_ParseTuple(args, "Oi", &o, &format_i) || get_format(format_i, &format)) return NULL;
    doc = transit_doc_new();
    if (!doc) return PyErr_NoMemory();
    v = from_py(doc, o, 0);
    if (v) {
        if (transit_write(v, format, &out, &err) != 0) PyErr_SetString(PyExc_ValueError, err.message);
        else if (format == TRANSIT_MSGPACK) r = PyBytes_FromStringAndSize((const char *)out.data, (Py_ssize_t)out.len);
        else r = PyUnicode_DecodeUTF8((const char *)out.data, (Py_ssize_t)out.len, "surrogatepass");
    }
    transit_buffer_free(&out);
    transit_doc_free(doc);
    return r;
}

/* Streams: values read from data fed in chunks as it arrives. A stream is a
 * capsule holding a transit_stream. */

#define STREAM_CAPSULE "transit._native.stream"

static void stream_destructor(PyObject *capsule) {
    transit_stream_free((transit_stream *)PyCapsule_GetPointer(capsule, STREAM_CAPSULE));
}

static PyObject *native_stream_new(PyObject *self, PyObject *args) {
    int format_i;
    transit_format format;
    transit_stream *s;
    PyObject *capsule;
    (void)self;
    if (!PyArg_ParseTuple(args, "i", &format_i) || get_format(format_i, &format)) return NULL;
    s = transit_stream_new(format, NULL, NULL);
    if (!s) return PyErr_NoMemory();
    capsule = PyCapsule_New(s, STREAM_CAPSULE, stream_destructor);
    if (!capsule) transit_stream_free(s);
    return capsule;
}

static transit_stream *get_stream(PyObject *capsule) {
    return (transit_stream *)PyCapsule_GetPointer(capsule, STREAM_CAPSULE);
}

static PyObject *native_stream_feed(PyObject *self, PyObject *args) {
    PyObject *capsule, *data;
    transit_stream *s;
    const char *buf;
    Py_ssize_t len;
    (void)self;
    if (!PyArg_ParseTuple(args, "OO", &capsule, &data) || !(s = get_stream(capsule))) return NULL;
    if (PyUnicode_Check(data)) {
        buf = PyUnicode_AsUTF8AndSize(data, &len);
        if (!buf) return NULL;
    } else if (PyBytes_Check(data)) {
        char *b;
        if (PyBytes_AsStringAndSize(data, &b, &len) < 0) return NULL;
        buf = b;
    } else {
        PyErr_SetString(PyExc_TypeError, "expected str or bytes");
        return NULL;
    }
    if (transit_stream_feed(s, buf, (size_t)len) != 0) return PyErr_NoMemory();
    Py_RETURN_NONE;
}

static PyObject *native_stream_end(PyObject *self, PyObject *capsule) {
    transit_stream *s = get_stream(capsule);
    (void)self;
    if (!s) return NULL;
    transit_stream_end(s);
    Py_RETURN_NONE;
}

/* (True, value) for the next complete value, or (False, None) if there
 * isn't one yet (or, after stream_end, at the end). */
static PyObject *native_stream_read(PyObject *self, PyObject *capsule) {
    transit_stream *s = get_stream(capsule);
    transit_doc *doc;
    transit_value *v;
    transit_error err;
    PyObject *value = NULL, *cache, *r;
    (void)self;
    if (!s) return NULL;
    doc = transit_doc_new();
    if (!doc) return PyErr_NoMemory();
    v = transit_stream_read(s, doc, &err);
    if (!v) {
        transit_doc_free(doc);
        if (err.code != TRANSIT_OK) {
            PyErr_SetString(PyExc_ValueError, err.message);
            return NULL;
        }
        return Py_BuildValue("(OO)", Py_False, Py_None);
    }
    cache = PyDict_New();
    if (cache) value = to_py(cache, v, 0);
    Py_XDECREF(cache);
    transit_doc_free(doc);
    if (!value) return NULL;
    r = Py_BuildValue("(ON)", Py_True, value);
    return r;
}

/* Module */

static PyMethodDef methods[] = {
    {"loads", native_loads, METH_VARARGS, "loads(data, format): decode transit (str or bytes)."},
    {"dumps", native_dumps, METH_VARARGS, "dumps(obj, format): encode as transit (str, or bytes for msgpack)."},
    {"stream_new", native_stream_new, METH_VARARGS, "stream_new(format): a stream to feed data to."},
    {"stream_feed", native_stream_feed, METH_VARARGS, "stream_feed(stream, data): add data (str or bytes)."},
    {"stream_end", native_stream_end, METH_O, "stream_end(stream): there's no more data."},
    {"stream_read", native_stream_read, METH_O,
     "stream_read(stream): (True, value) for the next value, or (False, None) if there isn't one yet."},
    {NULL, NULL, 0, NULL}};

static int exec_module(PyObject *m);

static PyModuleDef_Slot slots[] = {
    {Py_mod_exec, (void *)exec_module},
#ifdef Py_GIL_DISABLED
    /* safe without the GIL: no shared mutable state */
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}};

static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "transit._native", NULL, 0, methods,
                                    slots, NULL, NULL, NULL};

static int lookup(PyObject *mod, const char *name, PyObject **out) {
    *out = PyObject_GetAttrString(mod, name);
    return *out ? 0 : -1;
}

/* The classes and constants used above are looked up once, the first time
 * the module is loaded, and never change. */
static int exec_module(PyObject *m) {
    PyObject *tt = NULL, *uuid = NULL, *decimal = NULL, *datetime = NULL, *binascii = NULL, *utc = NULL;
    int ok;
    if (PyModule_AddStringConstant(m, "transit_c_version", TRANSIT_C_COMMIT) < 0) return -1;
    if (Unsupported) return PyModule_AddObjectRef(m, "Unsupported", Unsupported);
    tt = PyImport_ImportModule("transit.transit_types");
    uuid = PyImport_ImportModule("uuid");
    decimal = PyImport_ImportModule("decimal");
    datetime = PyImport_ImportModule("datetime");
    binascii = PyImport_ImportModule("binascii");
    ok = tt && uuid && decimal && datetime && binascii &&
         !lookup(tt, "Keyword", &Keyword) && !lookup(tt, "Symbol", &Symbol) && !lookup(tt, "URI", &URI) &&
         !lookup(tt, "TaggedValue", &TaggedValue) && !lookup(tt, "Link", &Link) &&
         !lookup(tt, "frozendict", &Frozendict) && !lookup(tt, "true", &T_true) && !lookup(tt, "false", &T_false) &&
         !lookup(uuid, "UUID", &UUID) && !lookup(decimal, "Decimal", &Decimal) &&
         !lookup(datetime, "datetime", &Datetime) && !lookup(datetime, "timedelta", &Timedelta) &&
         !lookup(binascii, "b2a_base64", &B2aBase64);
    if (ok) {
        PyObject *tz = PyObject_GetAttrString(datetime, "timezone");
        utc = tz ? PyObject_GetAttrString(tz, "utc") : NULL;
        Py_XDECREF(tz);
        Epoch = utc ? PyObject_CallFunction(Datetime, "iiiiiiiO", 1970, 1, 1, 0, 0, 0, 0, utc) : NULL;
        OneMs = PyObject_CallFunction(Timedelta, "iiii", 0, 0, 0, 1);
        Unsupported = PyErr_NewException("transit._native.Unsupported", NULL, NULL);
        ok = Epoch && OneMs && Unsupported && PyModule_AddObjectRef(m, "Unsupported", Unsupported) == 0;
    }
    Py_XDECREF(tt);
    Py_XDECREF(uuid);
    Py_XDECREF(decimal);
    Py_XDECREF(datetime);
    Py_XDECREF(binascii);
    Py_XDECREF(utc);
    return ok ? 0 : -1;
}

PyMODINIT_FUNC PyInit__native(void) { return PyModuleDef_Init(&module); }
