fn main() {
    tonic_build::compile_protos("proto/logs.proto").unwrap();
}