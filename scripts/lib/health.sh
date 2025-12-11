#!/bin/bash
# GT 2.0 Health Check and Service Status Functions
# Verify service availability and display access points

# Wait for services to stabilize
wait_for_stability() {
    local wait_time="${1:-10}"
    log_info "Waiting for services to stabilize..."
    sleep "$wait_time"
}

# Check if all services are healthy
check_all_services_healthy() {
    check_service_health
}

# Display access points
show_access_points() {
    echo ""
    log_success "Deployment Complete!"
    echo ""
    echo "🌐 Access Points:"
    echo "  • Control Panel: http://localhost:3001"
    echo "  • Tenant App:    http://localhost:3002"
    echo ""
    echo "📊 Service Status:"
    show_service_status
    echo ""
    echo "📊 View Logs: docker compose logs -f"
    echo ""
}

# Comprehensive health check with detailed output
health_check_detailed() {
    log_header "Health Check"

    # Check PostgreSQL databases
    log_info "Checking PostgreSQL databases..."
    if docker exec gentwo-controlpanel-postgres pg_isready -U postgres -d gt2_admin &>/dev/null; then
        log_success "Admin database: healthy"
    else
        log_error "Admin database: unhealthy"
    fi

    if docker exec gentwo-tenant-postgres-primary pg_isready -U postgres -d gt2_tenants &>/dev/null; then
        log_success "Tenant database: healthy"
    else
        log_error "Tenant database: unhealthy"
    fi

    # Check backend services
    log_info "Checking backend services..."
    if curl -sf http://localhost:8001/health &>/dev/null; then
        log_success "Control Panel backend: healthy"
    else
        log_warning "Control Panel backend: not responding"
    fi

    if curl -sf http://localhost:8002/health &>/dev/null; then
        log_success "Tenant backend: healthy"
    else
        log_warning "Tenant backend: not responding"
    fi

    if curl -sf http://localhost:8004/health &>/dev/null; then
        log_success "Resource cluster: healthy"
    else
        log_warning "Resource cluster: not responding"
    fi

    # Check overall container health
    check_all_services_healthy
}
