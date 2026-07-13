package de.robv.android.xposed;

import java.util.Set;

// Compile-only stub. Real implementation provided by the host app at runtime.
public final class XposedBridge {
    private XposedBridge() {}

    public static Set<XC_MethodHook.Unhook> hookAllMethods(
            Class<?> hookClass, String methodName, XC_MethodHook callback) {
        return null;
    }

    public static void log(String text) {}
    public static void log(Throwable t) {}
}
