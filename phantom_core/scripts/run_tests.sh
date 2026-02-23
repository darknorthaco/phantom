#!/bin/bash
# Phantom Distributed Compute Fabric - Test Runner
# Comprehensive test execution script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_DIR="tests"
COVERAGE_MIN=70
TIMEOUT=300

echo -e "${BLUE}🧪 Phantom Distributed Compute Fabric - Test Suite${NC}"
echo "=================================================="

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

# Check if pytest is available
if ! python3 -c "import pytest" &> /dev/null; then
    print_warning "pytest not found, installing..."
    pip install pytest pytest-cov pytest-timeout
fi

# Create test results directory
mkdir -p test_results

echo -e "\n${BLUE}📋 Test Configuration${NC}"
echo "Test Directory: $TEST_DIR"
echo "Coverage Minimum: $COVERAGE_MIN%"
echo "Timeout: ${TIMEOUT}s"

# Function to run specific test category
run_test_category() {
    local category=$1
    local test_file=$2
    local description=$3
    
    echo -e "\n${BLUE}🔍 Running $description${NC}"
    echo "----------------------------------------"
    
    if [ -f "$TEST_DIR/$test_file" ]; then
        python3 -m pytest "$TEST_DIR/$test_file" \
            --verbose \
            --timeout=$TIMEOUT \
            --tb=short \
            --junit-xml="test_results/${category}_results.xml" \
            --cov=phantom_core \
            --cov=linux_worker \
            --cov-report=term-missing \
            --cov-report=html:test_results/${category}_coverage
        
        if [ $? -eq 0 ]; then
            print_status "$description completed successfully"
        else
            print_error "$description failed"
            return 1
        fi
    else
        print_warning "$test_file not found, skipping $description"
    fi
}

# Function to check system dependencies
check_dependencies() {
    echo -e "\n${BLUE}🔧 Checking Dependencies${NC}"
    echo "----------------------------------------"
    
    # Check Python modules
    local required_modules=("flask" "requests" "psutil" "pyyaml")
    
    for module in "${required_modules[@]}"; do
        if python3 -c "import $module" &> /dev/null; then
            print_status "$module available"
        else
            print_warning "$module not available (some tests may be skipped)"
        fi
    done
    
    # Check GPU libraries (optional)
    if python3 -c "import pynvml" &> /dev/null; then
        print_status "NVIDIA GPU support available"
    else
        print_warning "NVIDIA GPU support not available (GPU tests may be skipped)"
    fi
    
    # Check system commands
    local commands=("curl" "ps" "netstat")
    for cmd in "${commands[@]}"; do
        if command -v $cmd &> /dev/null; then
            print_status "$cmd available"
        else
            print_warning "$cmd not available (some integration tests may be skipped)"
        fi
    done
}

# Function to run unit tests
run_unit_tests() {
    echo -e "\n${BLUE}🧪 Unit Tests${NC}"
    echo "----------------------------------------"
    
    run_test_category "unit" "test_controller.py" "Controller Unit Tests"
    run_test_category "unit" "test_workers.py" "Worker Unit Tests"
}

# Function to run integration tests
run_integration_tests() {
    echo -e "\n${BLUE}🔗 Integration Tests${NC}"
    echo "----------------------------------------"
    
    # Check if system is running
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        print_status "System is running, proceeding with integration tests"
        run_test_category "integration" "test_integration.py" "System Integration Tests"
    else
        print_warning "System not running, starting test instance..."
        
        # Start test instance
        python3 run.py --port 5001 &
        TEST_PID=$!
        
        # Wait for startup
        sleep 5
        
        # Run tests against test instance
        if curl -s http://localhost:5001/health > /dev/null 2>&1; then
            print_status "Test instance started successfully"
            # Modify test to use port 5001
            sed -i.bak 's/localhost:5000/localhost:5001/g' "$TEST_DIR/test_integration.py"
            run_test_category "integration" "test_integration.py" "System Integration Tests"
            # Restore original file
            mv "$TEST_DIR/test_integration.py.bak" "$TEST_DIR/test_integration.py"
        else
            print_error "Failed to start test instance"
        fi
        
        # Clean up test instance
        if [ ! -z "$TEST_PID" ]; then
            kill $TEST_PID 2>/dev/null || true
        fi
    fi
}

# Function to run performance tests
run_performance_tests() {
    echo -e "\n${BLUE}⚡ Performance Tests${NC}"
    echo "----------------------------------------"
    
    if [ -f "$TEST_DIR/test_performance.py" ]; then
        run_test_category "performance" "test_performance.py" "Performance Tests"
    else
        print_warning "Performance tests not implemented yet"
    fi
}

# Function to run security tests
run_security_tests() {
    echo -e "\n${BLUE}🔒 Security Tests${NC}"
    echo "----------------------------------------"
    
    if [ -f "$TEST_DIR/test_security.py" ]; then
        run_test_category "security" "test_security.py" "Security Tests"
    else
        print_warning "Security tests not implemented yet"
    fi
}

# Function to generate test report
generate_report() {
    echo -e "\n${BLUE}📊 Test Report${NC}"
    echo "----------------------------------------"
    
    # Count test results
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    
    if [ -d "test_results" ]; then
        for result_file in test_results/*_results.xml; do
            if [ -f "$result_file" ]; then
                local file_tests=$(grep -o 'tests="[0-9]*"' "$result_file" | grep -o '[0-9]*' || echo "0")
                local file_failures=$(grep -o 'failures="[0-9]*"' "$result_file" | grep -o '[0-9]*' || echo "0")
                local file_errors=$(grep -o 'errors="[0-9]*"' "$result_file" | grep -o '[0-9]*' || echo "0")
                
                total_tests=$((total_tests + file_tests))
                failed_tests=$((failed_tests + file_failures + file_errors))
            fi
        done
        
        passed_tests=$((total_tests - failed_tests))
        
        echo "Total Tests: $total_tests"
        echo "Passed: $passed_tests"
        echo "Failed: $failed_tests"
        
        if [ $failed_tests -eq 0 ]; then
            print_status "All tests passed! 🎉"
        else
            print_error "$failed_tests test(s) failed"
        fi
        
        # Coverage report
        if [ -d "test_results" ]; then
            echo -e "\n${BLUE}📈 Coverage Reports${NC}"
            echo "HTML coverage reports available in test_results/*_coverage/"
        fi
    else
        print_warning "No test results found"
    fi
}

# Main execution
main() {
    local run_all=true
    local run_unit=false
    local run_integration=false
    local run_performance=false
    local run_security=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --unit)
                run_all=false
                run_unit=true
                shift
                ;;
            --integration)
                run_all=false
                run_integration=true
                shift
                ;;
            --performance)
                run_all=false
                run_performance=true
                shift
                ;;
            --security)
                run_all=false
                run_security=true
                shift
                ;;
            --help)
                echo "Usage: $0 [--unit] [--integration] [--performance] [--security] [--help]"
                echo ""
                echo "Options:"
                echo "  --unit         Run only unit tests"
                echo "  --integration  Run only integration tests"
                echo "  --performance  Run only performance tests"
                echo "  --security     Run only security tests"
                echo "  --help         Show this help message"
                echo ""
                echo "If no options are specified, all available tests will be run."
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Check dependencies
    check_dependencies
    
    # Run selected test categories
    if [ "$run_all" = true ]; then
        run_unit_tests
        run_integration_tests
        run_performance_tests
        run_security_tests
    else
        [ "$run_unit" = true ] && run_unit_tests
        [ "$run_integration" = true ] && run_integration_tests
        [ "$run_performance" = true ] && run_performance_tests
        [ "$run_security" = true ] && run_security_tests
    fi
    
    # Generate final report
    generate_report
    
    echo -e "\n${BLUE}🏁 Test execution completed${NC}"
    echo "Test results and coverage reports available in test_results/"
}

# Run main function with all arguments
main "$@"