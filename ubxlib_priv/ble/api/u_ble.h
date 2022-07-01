/*
 * Copyright 2020 u-blox
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *  http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef _U_BLE_H_
#define _U_BLE_H_

/* No #includes allowed here */

/** @file
 * @brief This header file defines the general ble APIs,
 * basically initialise and deinitialise.
 */

#ifdef __cplusplus
extern "C" {
#endif

/* ----------------------------------------------------------------
 * COMPILE-TIME MACROS
 * -------------------------------------------------------------- */

#ifndef U_BLE_UART_BUFFER_LENGTH_BYTES
/** The recommended UART buffer length for the short range driver,
 * large enough for large AT or EDM packet using BLE.
 * Note: If module is also using WiFi, it is recommended to use that size.
 */
# define U_BLE_UART_BUFFER_LENGTH_BYTES 600
#endif

#ifndef U_BLE_AT_BUFFER_LENGTH_BYTES
/** The AT client buffer length required in the AT client by the
 * ble driver.
 */
# define U_BLE_AT_BUFFER_LENGTH_BYTES U_AT_CLIENT_BUFFER_LENGTH_BYTES
#endif

#ifndef U_BLE_UART_BAUD_RATE
/** The default baud rate to communicate with a short range module.
 */
# define U_BLE_UART_BAUD_RATE 115200
#endif

/* ----------------------------------------------------------------
 * TYPES
 * -------------------------------------------------------------- */

/** Error codes specific to ble.
 */
typedef enum {
    U_BLE_ERROR_FORCE_32_BIT = 0x7FFFFFFF,  /**< Force this enum to be 32 bit as it can be
                                                  used as a size also. */
    U_BLE_ERROR_AT = U_ERROR_BLE_MAX,      /**< -512 if U_ERROR_BASE is 0. */
    U_BLE_ERROR_NOT_CONFIGURED = U_ERROR_BLE_MAX - 1, /**< -511 if U_ERROR_BASE is 0. */
    U_BLE_ERROR_NOT_FOUND = U_ERROR_BLE_MAX - 2,  /**< -510 if U_ERROR_BASE is 0. */
    U_BLE_ERROR_INVALID_MODE = U_ERROR_BLE_MAX - 3,  /**< -509 if U_ERROR_BASE is 0. */
    U_BLE_ERROR_TEMPORARY_FAILURE = U_ERROR_BLE_MAX - 4  /**< -508 if U_ERROR_BASE is 0. */
} uBleErrorCode_t;

/* ----------------------------------------------------------------
 * FUNCTIONS
 * -------------------------------------------------------------- */

/** Initialise the ble.  If the driver is already
 * initialised then this function returns immediately.
 *
 * @return zero on success or negative error code on failure.
 */
int32_t uBleInit(void);

/** Shut-down ble.  All instances will be removed internally
 * with calls to uBleRemove().
 */
void uBleDeinit(void);

/** Add a ble instance.
 *
 * @param moduleType       the short range module type, if external module.
 *                         Otherwise just U_BLE_MODULE_TYPE_INTERNAL
 * @param atHandle         the handle of the AT client to use.  This must
 *                         already have been created by the caller with
 *                         a buffer of size U_BLE_AT_BUFFER_LENGTH_BYTES.
 *                         If a ble instance has already been added
 *                         for this atHandle an error will be returned.
 *                         In case of internal module:
 *                           just set the parameter to NULL.
 * @return                 on success the handle of the ble instance,
 *                         else negative error code.
 */
int32_t uBleAdd(uBleModuleType_t moduleType,
                uAtClientHandle_t atHandle);

/** Remove a ble instance.  It is up to the caller to ensure
 * that the short range module for the given instance has been disconnected
 * and/or powered down etc.; all this function does is remove the logical
 * instance.
 *
 * @param bleHandle  the handle of the ble instance to remove.
 */
void uBleRemove(int32_t bleHandle);

/** Get the handle of the AT client used by the given
 * ble instance.
 *
 * @param bleHandle   the handle of the ble instance.
 * @param pAtHandle   a place to put the AT client handle.
 * @return            zero on success else negative error code.
 */
int32_t uBleAtClientHandleGet(int32_t bleHandle,
                              uAtClientHandle_t *pAtHandle);

/** Detect the module connected to the handle. Will attempt to change the mode on
 * the module to communicate with it. No change to UART configuration is done,
 * so even if this fails with U_BLE_MODULE_TYPE_INVALID, as last attempt to recover,
 * it could work to re-init the UART on a different baud rate. This should recover
 * that module if another rate than the default one has been used.
 * If the response is U_BLE_MODULE_TYPE_UNSUPPORTED, the module repondes as expected but
 * does not support ble.
 *
 * @param bleHandle   the handle of the ble instance.
 * @return            Module on success, U_BLE_MODULE_TYPE_INVALID or U_BLE_MODULE_TYPE_UNSUPPORTED
 *                    on failure.
 */
uBleModuleType_t uBleDetectModule(int32_t bleHandle);

#ifdef __cplusplus
}
#endif

#endif // _U_BLE_H_

// End of file
