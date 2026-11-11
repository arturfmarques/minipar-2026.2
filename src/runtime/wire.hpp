// Codec binário tipado. Não interpreta código, nomes de comandos ou expressões.
namespace mp {
struct Writer {
    std::string bytes;
    void u32(std::uint32_t value) { for(int i=3;i>=0;--i) bytes.push_back(static_cast<char>((value>>(i*8))&255)); }
    void string(const std::string& value) {
        if(value.size()>frame_limit()) throw Error("String excede limite do protocolo");
        u32(static_cast<std::uint32_t>(value.size())); bytes+=value;
    }
};
struct Reader {
    const std::string& bytes;
    std::size_t position=0;
    void need(std::size_t length) { if(length>bytes.size()-position) throw Error("Payload truncado"); }
    std::uint32_t u32() {
        need(4); std::uint32_t value=0;
        for(int i=0;i<4;++i) value=(value<<8)|static_cast<unsigned char>(bytes[position++]);
        return value;
    }
    std::string string() { auto size=u32(); need(size); auto result=bytes.substr(position,size); position+=size; return result; }
    void end() { if(position!=bytes.size()) throw Error("Bytes adicionais no payload"); }
};
template<class T,class Enable=void> struct Codec;
template<> struct Codec<double> {
    static std::string name() { return "number"; }
    static void put(Writer& out,double value) {
        static_assert(sizeof(double)==8);
        out.string(name()); std::uint64_t bits=0; std::memcpy(&bits,&value,8);
        for(int i=7;i>=0;--i) out.bytes.push_back(static_cast<char>((bits>>(i*8))&255));
    }
    static double get(Reader& in) {
        if(in.string()!=name()) throw Error("Tipo recebido incompativel com number");
        in.need(8); std::uint64_t bits=0;
        for(int i=0;i<8;++i) bits=(bits<<8)|static_cast<unsigned char>(in.bytes[in.position++]);
        double value; std::memcpy(&value,&bits,8); return value;
    }
};
template<> struct Codec<std::int64_t> {
    static std::string name() { return "int64"; }
    static void put(Writer& out, std::int64_t value) {
        out.string(name()); auto bits=static_cast<std::uint64_t>(value);
        for(int i=7;i>=0;--i) out.bytes.push_back(static_cast<char>((bits>>(i*8))&255));
    }
    static std::int64_t get(Reader& in) {
        if(in.string()!=name()) throw Error("Tipo recebido incompativel com int64");
        in.need(8); std::uint64_t bits=0;
        for(int i=0;i<8;++i) bits=(bits<<8)|static_cast<unsigned char>(in.bytes[in.position++]);
        std::int64_t value; std::memcpy(&value,&bits,8); return value;
    }
};
template<> struct Codec<bool> {
    static std::string name() { return "bool"; }
    static void put(Writer& out,bool value) { out.string(name()); out.bytes.push_back(value?1:0); }
    static bool get(Reader& in) {
        if(in.string()!=name()) throw Error("Tipo recebido incompativel com bool");
        in.need(1); unsigned char value=in.bytes[in.position++];
        if(value>1) throw Error("Bool invalido"); return value!=0;
    }
};
template<> struct Codec<std::string> {
    static std::string name() { return "string"; }
    static void put(Writer& out,const std::string& value) { out.string(name()); out.string(value); }
    static std::string get(Reader& in) { if(in.string()!=name()) throw Error("Tipo recebido incompativel com string"); return in.string(); }
};
template<class T> struct Codec<std::vector<T>> {
    static std::string name() { return "list("+Codec<T>::name()+")"; }
    static void put(Writer& out,const std::vector<T>& values) {
        out.string(name()); out.u32(static_cast<std::uint32_t>(values.size()));
        for(const auto& value:values) Codec<T>::put(out,value);
    }
    static std::vector<T> get(Reader& in) {
        if(in.string()!=name()) throw Error("Tipo de colecao incompativel");
        auto count=in.u32();
        if(count>1000000 || count>in.bytes.size()-in.position) throw Error("Tamanho de colecao invalido");
        std::vector<T> result; result.reserve(count);
        for(std::uint32_t i=0;i<count;++i) result.push_back(Codec<T>::get(in));
        return result;
    }
};
template<> struct Codec<std::shared_ptr<MiniParChannel>> {
    static std::string name() { return "c_channel"; }
    static void put(Writer& out,const std::shared_ptr<MiniParChannel>& value) {
        if(!value) throw Error("Canal nulo");
        out.string(name()); out.string(value->ip); out.u32(value->port);
    }
    static std::shared_ptr<MiniParChannel> get(Reader& in) {
        if(in.string()!=name()) throw Error("Tipo de canal incompativel");
        auto host=in.string(); auto port=in.u32(); return std::make_shared<MiniParChannel>(host,port);
    }
};
template<class... T> std::string type_list() {
    std::string result;
    ((result+=(result.empty()?"":",")+Codec<T>::name()),...);
    return result;
}
template<class Tuple> std::string tuple_types() { return std::apply([](const auto&... value) { return type_list<std::decay_t<decltype(value)>...>(); },Tuple{}); }
template<class... T> std::tuple<T...> read_arguments(Reader& in) {
    if(in.u32()!=sizeof...(T)) throw Error("Aridade de argumentos invalida");
    return std::tuple<T...>{Codec<T>::get(in)...};
}
template<class Tuple> std::string write_arguments(const Tuple& values) {
    Writer out; out.u32(std::tuple_size_v<Tuple>);
    std::apply([&](const auto&... value) { (Codec<std::decay_t<decltype(value)>>::put(out,value),...); },values);
    return out.bytes;
}
}
