namespace mp {
template<class T,class Enable=void> struct Canonical { using type=std::decay_t<T>; };
template<class T> struct Canonical<T,std::enable_if_t<std::is_arithmetic_v<std::decay_t<T>> && !std::is_same_v<std::decay_t<T>,bool>>> { using type=double; };
template<> struct Canonical<std::int64_t> { using type=std::int64_t; };
template<> struct Canonical<const char*> { using type=std::string; };
template<> struct Canonical<char*> { using type=std::string; };
template<class T> struct Canonical<std::vector<T>> { using type=std::vector<typename Canonical<T>::type>; };
template<class T> using canonical_t=typename Canonical<std::decay_t<T>>::type;
struct SnapshotContext { std::unordered_map<const void*,std::shared_ptr<void>> copies; };
template<class T> T clone_field(const T& value,SnapshotContext& context);
template<class T> std::vector<T> clone_field(const std::vector<T>& value,SnapshotContext& context);
template<class T> std::shared_ptr<T> clone_field(const std::shared_ptr<T>& value,SnapshotContext& context);
template<class T> canonical_t<T> copy_value(const T& value,SnapshotContext& context);
template<class T> canonical_t<std::vector<T>> copy_value(const std::vector<T>& value,SnapshotContext& context);
template<class T> std::shared_ptr<T> copy_value(const std::shared_ptr<T>& value,SnapshotContext& context);

template<class T> canonical_t<T> copy_value(const T& value,SnapshotContext&) { return canonical_t<T>(value); }
template<class T> canonical_t<std::vector<T>> copy_value(const std::vector<T>& value,SnapshotContext& context) {
    canonical_t<std::vector<T>> result; result.reserve(value.size());
    for (const auto& item:value) result.push_back(copy_value(item,context));
    return result;
}
template<class T> std::shared_ptr<T> copy_value(const std::shared_ptr<T>& value,SnapshotContext& context) {
    if (!value) return {};
    if (auto it=context.copies.find(value.get());it!=context.copies.end()) return std::static_pointer_cast<T>(it->second);
    auto result=std::make_shared<T>(*value);
    context.copies[value.get()]=result;
    if constexpr (std::is_same_v<T,MiniParChannel>) {
        // Cópia do descritor: o único estado compartilhado é a comunicação explícita TCP.
    } else {
        static_assert(requires { value->__minipar_copy_into(*result,context); },"Objeto sem suporte a snapshot profundo");
        value->__minipar_copy_into(*result,context);
    }
    return result;
}
template<class T> auto snapshot(const T& value) { SnapshotContext context; return copy_value(value,context); }
template<class T> T clone_field(const T& value,SnapshotContext&) { return value; }
template<class T> std::vector<T> clone_field(const std::vector<T>& value,SnapshotContext& context) {
    std::vector<T> result; result.reserve(value.size());
    for(const auto& child:value) result.push_back(clone_field(child,context));
    return result;
}
template<class T> std::shared_ptr<T> clone_field(const std::shared_ptr<T>& value,SnapshotContext& context) { return copy_value(value,context); }
template<class T> auto snapshot_raw(T* value) {
    return snapshot(std::shared_ptr<T>(value,[](T*){}));
}
template<class Tuple> auto snapshot_tuple(const Tuple& values) {
    SnapshotContext context;
    return std::apply([&](const auto&... value) { return std::tuple{copy_value(value,context)...}; },values);
}
}
