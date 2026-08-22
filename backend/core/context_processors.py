def navigation(request):
    """Inject navigation items with active-page detection."""
    is_patrol_worker = (
        request.user.is_authenticated and
        request.user.groups.filter(name="patrol_worker").exists()
    )

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
        {
            'name': 'Readiness',
            'url': '/readiness/',
            'icon': 'readiness',
            'description': 'Operational Readiness Center',
        },
    ]

    # Add Patrol nav for workers and staff
    if request.user.is_authenticated:
        if is_patrol_worker:
            nav_items.append({
                'name': 'Patrol',
                'url': '/patrol/',
                'icon': 'patrol',
                'description': 'Track Inspection Patrol',
            })
        if request.user.is_staff:
            nav_items.append({
                'name': 'Patrol Review',
                'url': '/patrol/admin/',
                'icon': 'patrol',
                'description': 'Review Worker Patrols',
            })

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
        if item['url'] == '/admin/':
            item['active'] = current_path.startswith('/admin/')
        elif item['url'] == '/patrol/admin/':
            item['active'] = current_path.startswith('/patrol/admin/')
        elif item['url'] == '/patrol/':
            item['active'] = current_path.startswith('/patrol/') and not current_path.startswith('/patrol/admin/')
        else:
            item['active'] = current_path == item['url']

    return {
        'nav_items': nav_items,
        'is_controller': request.user.is_authenticated and request.user.is_staff,
        'is_patrol_worker': is_patrol_worker,
    }

def project_meta(request):
    return {
        "PROJECT_NAME": "Rakshak",
        "PROJECT_VERSION": "1.0",
        "project_name": "RAKSHAK",
        "project_subtitle": "Predictive Rail Maintenance",
    }
