"""Generic runtime API tests, separate from candidate documents and task answers."""


def generic_api_probe(root):
    doc = App.newDocument('GenericApiSyntaxProbe')
    path = root/'generic-api.FCStd'
    checks = {}
    try:
        obj = doc.addObject('Part::Box', 'Box')
        obj.Length, obj.Width, obj.Height = 3, 4, 5
        checks['properties_list_query'] = ('Length' in obj.PropertiesList and
                                          'NumericArea' not in obj.PropertiesList)
        checks['has_property_absent'] = not hasattr(obj, 'hasProperty')
        obj.addProperty('App::PropertyFloat', 'NumericArea')
        checks['properties_list_after_add'] = 'NumericArea' in obj.PropertiesList
        expressions = {'pi_constant': ('pi', math.pi), 'power_operator': ('2^3', 8),
                       'length_units': ('Length / (1 mm)', 3),
                       'area_units': ('Width * Height / (1 mm^2)', 20)}
        for name, (expression, expected) in expressions.items():
            obj.setExpression('NumericArea', expression)
            doc.recompute()
            checks[name] = math.isclose(obj.NumericArea, expected, abs_tol=1e-9)
        rejected = False
        try:
            obj.setExpression('NumericArea', 'math.pi ** 2')
        except Exception as exc:
            rejected = True
            checks['python_expression_error'] = type(exc).__name__
        checks['python_expression_rejected'] = rejected
        obj.setExpression('NumericArea', 'Width * Height / (1 mm^2)')
        doc.recompute()
        doc.saveAs(str(path))
    finally:
        App.closeDocument(doc.Name)
    file_sha = sha(path)
    doc = App.openDocument(str(path))
    try:
        obj = doc.getObject('Box')
        doc.recompute()
        checks['saved_reopened_value'] = math.isclose(obj.NumericArea, 20, abs_tol=1e-9)
        obj.Width = 6
        doc.recompute()
        checks['persisted_parameter_response'] = math.isclose(obj.NumericArea, 30, abs_tol=1e-9)
        checks['native_validity'] = obj.Shape.isValid()
    finally:
        App.closeDocument(doc.Name)
    checks['saved_file_unchanged'] = sha(path) == file_sha
    return {'status': 'PASS' if all(v is True for k, v in checks.items()
                                   if k != 'python_expression_error') else 'FAIL',
            'checks': checks, 'expressions': {k: v[0] for k, v in expressions.items()},
            'freecad_version': list(App.Version()), 'scope': 'generic box API syntax only',
            'file_sha256': file_sha}
