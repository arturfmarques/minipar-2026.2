_CPP_BASE = """\
#include <iostream>
#include <string>
#include <sstream>
#include <vector>
#include <thread>
#include <memory>
#include <cstring>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <type_traits>
#include <exception>
#include <random>
#include <utility>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <stdexcept>
#include <atomic>

#include <cstdint>
#include <limits>

template<class T> std::int64_t __minipar_int(T value) {
    if constexpr (std::is_arithmetic_v<T> && !std::is_same_v<T, bool>) {
        if constexpr (std::is_same_v<T, std::int64_t>) return value;
        long double number = static_cast<long double>(value);
        if (std::isfinite(number) && number == std::floor(number) &&
            number >= -9223372036854775808.0L && number < 9223372036854775808.0L)
            return static_cast<std::int64_t>(value);
    }
    throw std::runtime_error("int exige inteiro assinado de 64 bits, sem truncamento");
}
std::int64_t __minipar_int_add(std::int64_t a, std::int64_t b) {
    std::int64_t result;
    if (__builtin_add_overflow(a, b, &result)) throw std::runtime_error("Overflow de int em soma");
    return result;
}
std::int64_t __minipar_int_sub(std::int64_t a, std::int64_t b) {
    std::int64_t result;
    if (__builtin_sub_overflow(a, b, &result)) throw std::runtime_error("Overflow de int em subtracao");
    return result;
}
std::int64_t __minipar_int_mul(std::int64_t a, std::int64_t b) {
    std::int64_t result;
    if (__builtin_mul_overflow(a, b, &result)) throw std::runtime_error("Overflow de int em multiplicacao");
    return result;
}
std::int64_t __minipar_int_mod(std::int64_t a, std::int64_t b) {
    if (!b) throw std::runtime_error("Modulo de int por zero");
    if (a == std::numeric_limits<std::int64_t>::min() && b == -1) return 0;
    auto result = a % b;
    return result && ((result < 0) != (b < 0)) ? result + b : result;
}

inline std::atomic<int> __minipar_program_status{0};
void __minipar_set_exit_code(double status) {
    if (!std::isfinite(status) || status != std::floor(status) || status < 0 || status > 255)
        throw std::runtime_error("Codigo de saida deve ser inteiro entre 0 e 255");
    __minipar_program_status.store(static_cast<int>(status));
}

double __minipar_monotonic() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
template<class T> std::string __minipar_text(const T& value) {
    std::ostringstream stream;
    stream << std::setprecision(17) << std::boolalpha << value;
    return stream.str();
}
std::string __minipar_get_env(const std::string& name, const std::string& fallback) {
    if (name.empty() || name.find(char(0)) != std::string::npos)
        throw std::runtime_error("Nome de variavel de ambiente invalido");
    const char* value = std::getenv(name.c_str());
    return value ? std::string(value) : fallback;
}
void __minipar_require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}
void __minipar_write_text(const std::string& filename, const std::string& text) {
    if (filename.empty() || filename.find(char(0)) != std::string::npos)
        throw std::runtime_error("Caminho de arquivo invalido");
    try {
        std::ofstream file;
        file.exceptions(std::ios::failbit | std::ios::badbit);
        file.open(std::filesystem::path(std::u8string(filename.begin(), filename.end())), std::ios::binary | std::ios::trunc);
        file.write(text.data(), static_cast<std::streamsize>(text.size()));
        file.flush();
        file.close();
    } catch (const std::exception& error) {
        throw std::runtime_error("Falha ao escrever arquivo '" + filename + "': " + error.what());
    }
}

bool __minipar_try_write_text(const std::string& filename, const std::string& text) {
    try { __minipar_write_text(filename, text); return true; }
    catch (const std::exception&) { return false; }
}

// Helper para Random nativo
double random_val() {
    thread_local std::mt19937_64 generator(std::random_device{}());
    return std::uniform_real_distribution<double>(0.0,1.0)(generator);
}

template<class A,class B> auto __minipar_mod(A a,B b) {
    if (b==0) throw std::runtime_error("Modulo por zero");
    if constexpr(std::is_integral_v<A> && std::is_integral_v<B>) return a % b;
    else return std::fmod(a,b);
}

template<class A, class B> double __minipar_div(A a, B b) {
    if (b == 0) throw std::runtime_error("Divisao por zero");
    return static_cast<double>(a) / static_cast<double>(b);
}

// MiniPar number e comprimentos sao valores numericos, nunca size_t sem sinal.
template<class Container, class Index>
decltype(auto) __minipar_at(Container&& values, Index index, int line, int column) {
    double position = static_cast<double>(index);
    if (!std::isfinite(position) || position < 0 || std::floor(position) != position ||
        position >= static_cast<double>(values.size()))
        throw std::runtime_error("Indice fora dos limites/invalido em " + std::to_string(line) + ":" +
            std::to_string(column) + ": " + std::to_string(position) +
            "; tamanho=" + std::to_string(values.size()));
    return std::forward<Container>(values).at(static_cast<std::size_t>(position));
}

template<class T> using __minipar_element = std::conditional_t<
    std::is_arithmetic_v<std::decay_t<T>> && !std::is_same_v<std::decay_t<T>, bool>, double, std::decay_t<T>>;
inline std::vector<double> __minipar_list() { return {}; }
template<class... Args> auto __minipar_list(Args... values) {
    using Element = std::common_type_t<__minipar_element<Args>...>;
    return std::vector<Element>{static_cast<Element>(std::move(values))...};
}

// init e um metodo MiniPar: a fabrica mantem construcao padrao para snapshots.
template<class T, class... Args> std::shared_ptr<T> __minipar_new(Args&&... arguments) {
    auto object = std::make_shared<T>();
    if constexpr (requires { object->init(std::forward<Args>(arguments)...); })
        object->init(std::forward<Args>(arguments)...);
    else static_assert(sizeof...(Args) == 0, "Classe sem inicializador compativel");
    return object;
}

// Helper para Input
std::string input() {
    std::string s;
    std::getline(std::cin, s);
    return s;
}

std::string input(const std::string& prompt) {
    std::cout << prompt;
    return input();
}

// Converte linha com inteiros separados por espaco em vetor (ex.: "10 -3 80")
std::vector<double> __parse_ints(const std::string& s) {
    std::vector<double> result;
    std::istringstream iss(s);
    double n;
    while (iss >> n) {
        result.push_back(n);
    }
    if (!iss.eof()) throw std::runtime_error("Entrada numerica invalida em parse_ints");
    return result;
}

std::vector<int> __minipar_range(int end) {
    std::vector<int> values;
    for (int i = 0; i < end; ++i) values.push_back(i);
    return values;
}

std::vector<int> __minipar_range(int start, int end) {
    std::vector<int> values;
    for (int i = start; i < end; ++i) values.push_back(i);
    return values;
}

// Helper para Arrays (.pop) do Python
template<typename T>
auto __array_pop(std::vector<T>& v) {
    if (v.empty()) throw std::runtime_error("pop de lista vazia");
    auto val = v.back();
    v.pop_back();
    return val;
}

// Helper para formatar e printar std::vector (arrays e matrizes) nativamente
template <typename T>
std::ostream& operator<<(std::ostream& os, const std::vector<T>& v) {
    os << "[";
    for (size_t i = 0; i < v.size(); ++i) {
        os << v[i];
        if (i != v.size() - 1) os << ", ";
    }
    os << "]";
    return os;
}

template<typename T>
std::string __to_string(const T& val) {
    if constexpr (std::is_constructible_v<std::string, T>) {
        return std::string(val);
    } else {
        return std::to_string(val);
    }
}

template<typename T>
auto __make_matrix(int rows, int cols, T init_val) {
    using ActualT = std::conditional_t<std::is_same_v<std::decay_t<T>, const char*>, std::string, T>;
    return std::vector<std::vector<ActualT>>(rows, std::vector<ActualT>(cols, init_val));
}

"""


from pathlib import Path

_RUNTIME_DIR = Path(__file__).with_name('runtime')
_RUNTIME_PARTS = ('net.hpp', 'affinity.hpp', 'channel.hpp', 'snapshot.hpp', 'tasks.hpp', 'wire.hpp', 'rpc.hpp')
_CPP_HEADER = _CPP_BASE + '\n' + '\n'.join((_RUNTIME_DIR / name).read_text(encoding='utf-8') for name in _RUNTIME_PARTS)
