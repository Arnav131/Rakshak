def navigation(request):
    """Inject navigation items with active-page detection."""
    nav_items = [
        {
            'name': 'Dashboard',
            'url': '/',
            'icon': 'dashboard',
            'description': 'System Overview',
        },
        {
            'name': 'Alerts',
            'url': '/alerts/',
            'icon': 'alerts',
            'description': 'Active Alerts',
        },
        {
            'name': 'Tickets',
            'url': '/tickets/',
            'icon': 'tickets',
            'description': 'Maintenance Tickets',
        },
        {
            'name': 'Map',
            'url': '/map/',
            'icon': 'map',
            'description': 'Railway Network',
        },
    ]

    # Add controller-only tools for staff users
    if request.user.is_authenticated and request.user.is_staff:
        nav_items.append({
            'name': 'Simulation',
            'url': '/simulation/',
            'icon': 'simulation',
            'description': 'Live Journey Simulation',
        })
        nav_items.append({
            'name': 'Admin',
            'url': '/admin/',
            'icon': 'admin',
            'description': 'Control & Audit',
        })

    # Detect active page
    current_path = request.path
    for item in nav_items:
        item['active'] = (
            current_path == item['url'] or
            (item['url'] == '/admin/' and current_path.startswith('/admin/'))
        )

    return {
        'nav_items': nav_items,
        'is_controller': request.user.is_authenticated and request.user.is_staff
    }

def project_meta(request):
    return {
        "PROJECT_NAME": "Rakshak",
        "PROJECT_VERSION": "1.0",
        "project_name": "RAKSHAK",
        "project_subtitle": "Predictive Rail Maintenance",
    }
