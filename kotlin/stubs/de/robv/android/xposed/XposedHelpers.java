package de.robv.android.xposed;

// Compile-only stub. Real implementation provided by the host app at runtime.
public final class XposedHelpers {
    private XposedHelpers() {}

    public static Class<?> findClass(String className, ClassLoader classLoader) { return null; }
    public static Object getObjectField(Object obj, String fieldName) { return null; }
    public static void setObjectField(Object obj, String fieldName, Object value) {}
    public static int getIntField(Object obj, String fieldName) { return 0; }
    public static int getStaticIntField(Class<?> clazz, String fieldName) { return 0; }
    public static Object getStaticObjectField(Class<?> clazz, String fieldName) { return null; }
    public static Object callMethod(Object obj, String methodName, Object... args) { return null; }
    public static Object callStaticMethod(Class<?> clazz, String methodName, Object... args) { return null; }
    public static Object newInstance(Class<?> clazz, Object... args) { return null; }
}
